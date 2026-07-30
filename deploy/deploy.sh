#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGION="${COURSEWARE_OSS_REGION:-cn-hangzhou}"
BUCKET="${COURSEWARE_OSS_BUCKET:-}"
FUNCTION="${COURSEWARE_FC_FUNCTION:-courseware-space-generator}"
TRIGGER="${COURSEWARE_FC_TRIGGER:-courseware-space-http}"
ROLE="${COURSEWARE_FC_ROLE:-courseware-space-fc-role}"
POLICY="${COURSEWARE_FC_POLICY:-courseware-space-oss-staging-write}"
CPU="${COURSEWARE_FC_CPU:-0.5}"
CORS_ORIGINS="${COURSEWARE_CORS_ORIGINS:-https://landeermail.github.io}"
RATE_PER_CLIENT="${COURSEWARE_RATE_LIMIT_PER_CLIENT:-30}"
RATE_GLOBAL="${COURSEWARE_RATE_LIMIT_GLOBAL:-80}"
RATE_WINDOW="${COURSEWARE_RATE_LIMIT_WINDOW:-600}"
CLI="${ALIYUN_CLI:-$(command -v aliyun || printf '')}"

for variable in ALIBABA_CLOUD_ACCESS_KEY_ID ALIBABA_CLOUD_ACCESS_KEY_SECRET KIMI_API_KEY; do
  if [[ -z "${!variable:-}" ]]; then
    printf '缺少环境变量：%s\n' "$variable" >&2
    exit 1
  fi
done
if [[ -z "$CLI" || ! -x "$CLI" ]]; then
  printf '未找到阿里云 CLI 3.3.0+；请设置 ALIYUN_CLI。\n' >&2
  exit 1
fi
if [[ "$BUCKET" != courseware-space-* || "$FUNCTION" != courseware-space-* || "$TRIGGER" != courseware-space-* || "$ROLE" != courseware-space-* || "$POLICY" != courseware-space-* ]]; then
  printf '所有云资源名称必须使用 courseware-space-* 前缀。\n' >&2
  exit 1
fi
if [[ ! "$CPU" =~ ^(0\.[0-9]+|[1-9][0-9]*(\.[0-9]+)?)$ ]]; then
  printf 'COURSEWARE_FC_CPU 必须是正数。\n' >&2
  exit 1
fi
if [[ "$CORS_ORIGINS" != https://* && "$CORS_ORIGINS" != http://* ]]; then
  printf 'COURSEWARE_CORS_ORIGINS 必须是 HTTP(S) Origin。\n' >&2
  exit 1
fi
if [[ ! "$RATE_PER_CLIENT" =~ ^[1-9][0-9]*$ || ! "$RATE_GLOBAL" =~ ^[1-9][0-9]*$ || ! "$RATE_WINDOW" =~ ^[1-9][0-9]*$ || "$RATE_PER_CLIENT" -gt "$RATE_GLOBAL" ]]; then
  printf '限流配置必须是正整数，且单客户端上限不能超过全局上限。\n' >&2
  exit 1
fi

export ALIBABA_CLOUD_IGNORE_PROFILE=TRUE
export ALIBABA_CLOUD_REGION_ID="$REGION"
export OSS_ACCESS_KEY_ID="$ALIBABA_CLOUD_ACCESS_KEY_ID"
export OSS_ACCESS_KEY_SECRET="$ALIBABA_CLOUD_ACCESS_KEY_SECRET"
export PYTHONWARNINGS=ignore

CONTROL_DIR="$(mktemp -d /tmp/courseware-deploy-control.XXXXXX)"
python3 -m pip install --disable-pip-version-check --no-input --target "$CONTROL_DIR" 'alibabacloud-oss-v2==1.3.2' >/dev/null

"$ROOT/deploy/build_package.sh"
PYTHONPATH="$CONTROL_DIR" python3 "$ROOT/deploy/oss_bootstrap.py" ensure
PYTHONPATH="$CONTROL_DIR" python3 "$ROOT/deploy/oss_bootstrap.py" upload-code --package "$ROOT/deploy/dist/courseware-space-fc.zip"
code_sha="$(shasum -a 256 "$ROOT/deploy/dist/courseware-space-fc.zip" | awk '{print $1}')"
code_object="deploy/code/$code_sha.zip"

trust_policy='{"Version":"1","Statement":[{"Effect":"Allow","Principal":{"Service":["fc.aliyuncs.com"]},"Action":"sts:AssumeRole"}]}'
runtime_policy="$(jq -nc --arg bucket "$BUCKET" '{Version:"1",Statement:[{Effect:"Allow",Action:["oss:PutObject","oss:PutObjectAcl"],Resource:[("acs:oss:*:*:"+$bucket+"/staging/*")]}]}')"

if role_result="$("$CLI" ram get-role --role-name "$ROLE" 2>&1)"; then
  printf 'ram_role=existing\n'
elif [[ "$role_result" == *"EntityNotExist.Role"* ]]; then
  "$CLI" ram create-role --role-name "$ROLE" --assume-role-policy-document "$trust_policy" --description 'Courseware Space FC OSS staging role' >/dev/null
  printf 'ram_role=created\n'
else
  printf '读取 RAM role 失败：%s\n' "$role_result" >&2
  exit 1
fi
role_result="$("$CLI" ram get-role --role-name "$ROLE")"
role_arn="$(printf '%s' "$role_result" | jq -r '.Role.Arn')"
if [[ -z "$role_arn" || "$role_arn" == "null" ]]; then
  printf '无法读取 RAM role ARN。\n' >&2
  exit 1
fi

if policy_result="$("$CLI" ram get-policy --policy-name "$POLICY" --policy-type Custom 2>&1)"; then
  printf 'ram_policy=existing\n'
elif [[ "$policy_result" == *"EntityNotExist.Policy"* ]]; then
  "$CLI" ram create-policy --policy-name "$POLICY" --policy-document "$runtime_policy" --description 'Write only Courseware Space OSS staging objects' >/dev/null
  printf 'ram_policy=created\n'
else
  printf '读取 RAM policy 失败：%s\n' "$policy_result" >&2
  exit 1
fi
if attach_result="$("$CLI" ram attach-policy-to-role --policy-type Custom --policy-name "$POLICY" --role-name "$ROLE" 2>&1)"; then
  printf 'ram_policy_attachment=ok\n'
elif [[ "$attach_result" == *"EntityAlreadyExists"* || "$attach_result" == *"already attached"* ]]; then
  printf 'ram_policy_attachment=existing\n'
else
  printf '绑定 RAM policy 失败：%s\n' "$attach_result" >&2
  exit 1
fi

runtime_config='{"command":["/code/bootstrap"],"port":9000,"healthCheckConfig":{"httpGetUrl":"/api/health","initialDelaySeconds":2,"periodSeconds":10,"timeoutSeconds":3,"failureThreshold":3,"successThreshold":1}}'
function_env=(
  "KIMI_API_KEY=$KIMI_API_KEY"
  "COURSEWARE_CLOUD_MODE=1"
  "COURSEWARE_OSS_BUCKET=$BUCKET"
  "COURSEWARE_OSS_REGION=$REGION"
  "COURSEWARE_OSS_ENDPOINT=https://oss-$REGION-internal.aliyuncs.com"
  "COURSEWARE_MAX_WORKERS=1"
  "COURSEWARE_CORS_ORIGINS=$CORS_ORIGINS"
  "COURSEWARE_RATE_LIMIT_PER_CLIENT=$RATE_PER_CLIENT"
  "COURSEWARE_RATE_LIMIT_GLOBAL=$RATE_GLOBAL"
  "COURSEWARE_RATE_LIMIT_WINDOW=$RATE_WINDOW"
)
code_config=("ossBucketName=$BUCKET" "ossObjectName=$code_object")

if function_result="$("$CLI" fc get-function --region "$REGION" --function-name "$FUNCTION" 2>&1)"; then
  "$CLI" fc update-function --region "$REGION" --function-name "$FUNCTION" \
    --code "${code_config[@]}" \
    --custom-runtime-config "$runtime_config" \
    --environment-variables "${function_env[@]}" \
    --role "$role_arn" --timeout 180 --memory-size 1024 --cpu "$CPU" --disk-size 512 \
    --instance-concurrency 8 --internet-access true >/dev/null
  printf 'fc_function=updated\n'
elif [[ "$function_result" == *"FunctionNotFound"* || "$function_result" == *"not found"* ]]; then
  "$CLI" fc create-function --region "$REGION" --function-name "$FUNCTION" \
    --handler unused --runtime custom.debian12 \
    --code "${code_config[@]}" \
    --custom-runtime-config "$runtime_config" \
    --environment-variables "${function_env[@]}" \
    --role "$role_arn" --timeout 180 --memory-size 1024 --cpu "$CPU" --disk-size 512 \
    --instance-concurrency 8 --internet-access true \
    --description 'Courseware Space generator web function' >/dev/null
  printf 'fc_function=created\n'
else
  printf '读取 FC function 失败：%s\n' "$function_result" >&2
  exit 1
fi

trigger_config='{"authType":"anonymous","methods":["GET","POST","HEAD","OPTIONS"],"disableURLInternet":false}'
if trigger_result="$("$CLI" fc get-trigger --region "$REGION" --function-name "$FUNCTION" --trigger-name "$TRIGGER" 2>&1)"; then
  printf 'fc_trigger=existing\n'
elif [[ "$trigger_result" == *"TriggerNotFound"* || "$trigger_result" == *"not found"* ]]; then
  "$CLI" fc create-trigger --region "$REGION" --function-name "$FUNCTION" --trigger-name "$TRIGGER" --trigger-type http --trigger-config "$trigger_config" >/dev/null
  printf 'fc_trigger=created\n'
else
  printf '读取 FC trigger 失败：%s\n' "$trigger_result" >&2
  exit 1
fi

"$CLI" fc put-concurrency-config --region "$REGION" --function-name "$FUNCTION" --reserved-concurrency 1 >/dev/null
printf 'fc_reserved_concurrency=1\n'

trigger_result="$("$CLI" fc get-trigger --region "$REGION" --function-name "$FUNCTION" --trigger-name "$TRIGGER")"
public_url="$(printf '%s' "$trigger_result" | jq -r '.httpTrigger.urlInternet // .urlInternet // .UrlInternet // empty')"
jq -n --arg region "$REGION" --arg bucket "$BUCKET" --arg function "$FUNCTION" --arg trigger "$TRIGGER" --arg public_url "$public_url" --arg code_object "$code_object" \
  '{region:$region,bucket:$bucket,function:$function,trigger:$trigger,public_url:$public_url,code_object:$code_object}' > "$ROOT/deploy/dist/cloud-state.json"
printf 'public_url=%s\n' "${public_url:-not-returned-by-api}"
printf 'deploy_status=ok\n'
