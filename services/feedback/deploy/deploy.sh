#!/usr/bin/env bash
# Feedback-only cutover plan for the existing public FC function.
# Default is a desensitized dry-run: it prints the auditable plan and performs
# zero cloud calls. Real writes require an explicit --apply, a current
# BLOCKED.md check, completed bounded review, and explicit product authorization.
set -euo pipefail

MODULE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REGION="${COURSEWARE_OSS_REGION:-cn-hangzhou}"
FEEDBACK_BUCKET="${COURSEWARE_FEEDBACK_OSS_BUCKET:-}"
FUNCTION="${COURSEWARE_FC_FUNCTION:-courseware-space-generator}"
TRIGGER="${COURSEWARE_FC_TRIGGER:-courseware-space-http}"
ROLE="${COURSEWARE_FC_FEEDBACK_ROLE:-courseware-space-fc-feedback-role}"
POLICY="${COURSEWARE_FC_FEEDBACK_POLICY:-courseware-space-fc-feedback-write}"
CPU="${COURSEWARE_FC_CPU:-0.5}"
CORS_ORIGINS="${COURSEWARE_CORS_ORIGINS:-https://landeermail.github.io}"
RATE_PER_CLIENT="${COURSEWARE_RATE_LIMIT_PER_CLIENT:-30}"
RATE_GLOBAL="${COURSEWARE_RATE_LIMIT_GLOBAL:-80}"
RATE_WINDOW="${COURSEWARE_RATE_LIMIT_WINDOW:-600}"
CLI="${ALIYUN_CLI:-$(command -v aliyun || printf '')}"
PACKAGE="${COURSEWARE_FEEDBACK_PACKAGE:-$MODULE_ROOT/dist/courseware-space-feedback-fc.zip}"
TEACHER_STORAGE_KEY="${COURSEWARE_TEACHER_STORAGE_KEY:-}"

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    *)
      printf '未知参数：%s（仅支持 --apply）\n' "$arg" >&2
      exit 1
      ;;
  esac
done

# ---- 前置校验：任何失败都在计划输出与写命令之前退出 ----
if [[ ! "${COURSEWARE_ACCESS_CODE:-}" =~ ^[A-Za-z0-9]{48}$ ]]; then
  printf 'COURSEWARE_ACCESS_CODE 必须是 48 位大小写字母或数字。\n' >&2
  exit 1
fi
if [[ ! "$TEACHER_STORAGE_KEY" =~ ^[0-9a-f]{64}$ ]]; then
  printf 'COURSEWARE_TEACHER_STORAGE_KEY 必须是现有老师评价目录的 SHA-256。\n' >&2
  exit 1
fi
if [[ ! "$FEEDBACK_BUCKET" =~ ^courseware-space-private-[a-z0-9-]+$ ]]; then
  printf 'COURSEWARE_FEEDBACK_OSS_BUCKET 必须是 courseware-space-private-* bucket。\n' >&2
  exit 1
fi
if [[ "$FUNCTION" != courseware-space-* || "$TRIGGER" != courseware-space-* || "$ROLE" != courseware-space-* || "$POLICY" != courseware-space-* ]]; then
  printf '所有云资源名称必须使用 courseware-space-* 前缀。\n' >&2
  exit 1
fi
if [[ ! "$REGION" =~ ^cn-[a-z0-9-]+$ ]]; then
  printf 'COURSEWARE_OSS_REGION 无效。\n' >&2
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
if [[ -z "$CLI" || ! -x "$CLI" ]]; then
  printf '未找到阿里云 CLI 3.3.0+；请设置 ALIYUN_CLI。\n' >&2
  exit 1
fi
kimi_env="$(env | cut -d= -f1 | grep -i '^kimi' || true)"
if [[ -n "$kimi_env" ]]; then
  printf 'feedback-only 部署环境中不允许存在 Kimi 变量：%s\n' "$kimi_env" >&2
  exit 1
fi
if [[ ! -f "$PACKAGE" ]]; then
  printf 'feedback-only 部署包不存在；请先运行 services/feedback/deploy/build_package.sh。\n' >&2
  exit 1
fi
# 实际待部署 ZIP（包括环境变量指定的自定义包）必须通过同一白名单审计；
# 审计失败立即退出：不调用 CLI、不输出计划或任何“包无 Kimi/生成代码”的成功主张。
if ! bash "$MODULE_ROOT/deploy/build_package.sh" --audit-only "$PACKAGE"; then
  printf '待部署包未通过白名单审计，已停止；未进行任何云端调用。\n' >&2
  exit 1
fi
if [[ "$APPLY" == "1" ]]; then
  for variable in ALIBABA_CLOUD_ACCESS_KEY_ID ALIBABA_CLOUD_ACCESS_KEY_SECRET; do
    if [[ -z "${!variable:-}" ]]; then
      printf '缺少环境变量：%s\n' "$variable" >&2
      exit 1
    fi
  done
  if [[ "${COURSEWARE_OSS_BUCKET:-}" != courseware-space-* ]]; then
    printf 'apply 需要 COURSEWARE_OSS_BUCKET（courseware-space-*，仅用于存放代码对象）。\n' >&2
    exit 1
  fi
fi

# ---- 脱敏计划：不输出真实 URL、bucket 后缀、访问码或账号 ----
package_sha="$(shasum -a 256 "$PACKAGE" | awk '{print $1}')"
masked_bucket="courseware-space-private-***"
env_keys=(
  COURSEWARE_CLOUD_MODE
  COURSEWARE_FEEDBACK_OSS_BUCKET
  COURSEWARE_OSS_REGION
  COURSEWARE_OSS_ENDPOINT
  COURSEWARE_CORS_ORIGINS
  COURSEWARE_RATE_LIMIT_PER_CLIENT
  COURSEWARE_RATE_LIMIT_GLOBAL
  COURSEWARE_RATE_LIMIT_WINDOW
  COURSEWARE_ACCESS_CODE
  COURSEWARE_TEACHER_STORAGE_KEY
)

if [[ "$APPLY" == "1" ]]; then
  printf 'mode=apply\n'
else
  printf 'mode=dry-run\n'
fi
printf 'package_sha256=%s\n' "$package_sha"
printf 'fc_function=%s（原位切换，保留现有函数与触发器 URL，不在本输出打印）\n' "$FUNCTION"
printf 'fc_trigger=%s trigger_url=preserved-not-printed\n' "$TRIGGER"
printf 'ram_role=%s（独立 feedback 运行角色，不复用生成角色）\n' "$ROLE"
printf 'ram_policy=%s\n' "$POLICY"
printf 'policy_actions=oss:PutObject,oss:GetObject,oss:ListObjects\n'
printf 'policy_write_resource=acs:oss:*:*:%s/feedback/*\n' "$masked_bucket"
printf 'policy_read_resources=acs:oss:*:*:%s/feedback/tasks/*,acs:oss:*:*:%s/feedback/reviews/*\n' "$masked_bucket" "$masked_bucket"
printf 'policy_list_prefixes=feedback/tasks/*,feedback/reviews/*\n'
printf 'policy_staging_grants=0\n'
printf 'function_env_keys=%s\n' "${env_keys[*]}"
printf 'kimi_env_vars=0\n'
printf 'package_kimi_refs=0 package_generator_refs=0\n'
printf 'access_code=set-not-printed\n'
printf 'teacher_storage_key=set-not-printed\n'
printf 'account=not-printed\n'
if [[ "$APPLY" != "1" ]]; then
  printf 'cloud_changes=0\n'
  printf '下一步：重读 BLOCKED.md，确认有界复核通过并取得明确授权后，显式加 --apply 执行。\n'
  exit 0
fi

# ---- 以下仅显式 --apply 到达 ----
export ALIBABA_CLOUD_IGNORE_PROFILE=TRUE
export ALIBABA_CLOUD_REGION_ID="$REGION"

fail_stop() {
  printf '%s\n' "$1" >&2
  exit 1
}

url_decode() {
  python3 -c 'import sys, urllib.parse; print(urllib.parse.unquote(sys.stdin.read()), end="")'
}

# 任务 1：任何云端写命令前核验调用者身份；主账号/root、查询失败、
# 空白或无法解析一律失败关闭；错误信息不打印账号、AccessKey 或身份原文。
if ! identity_result="$("$CLI" sts GetCallerIdentity 2>&1)"; then
  fail_stop '无法确认部署调用者身份，已停止；未进行任何写操作。'
fi
identity_arn="$(printf '%s' "$identity_result" | jq -r '.Arn // empty' 2>/dev/null || true)"
if [[ -z "$identity_arn" ]]; then
  fail_stop '部署调用者身份响应无法解析，已停止；未进行任何写操作。'
fi
if [[ "$identity_arn" =~ ^acs:ram::[0-9]+:root$ ]]; then
  fail_stop '部署入口拒绝阿里云主账号（root）身份；请改用专用最小权限 RAM 部署用户。'
fi
if [[ ! "$identity_arn" =~ ^acs:ram::[0-9]+:user/[a-zA-Z0-9_.@-]+$ && ! "$identity_arn" =~ ^acs:sts::[0-9]+:assumed-role/[a-zA-Z0-9_.@-]+/[a-zA-Z0-9_.@-]+$ ]]; then
  fail_stop '部署调用者不是已核验的 RAM 用户或角色会话，已停止；未进行任何写操作。'
fi
printf 'deploy_identity=ram-principal（脱敏，不打印账号）\n'

# 任务 2：feedback role 与 custom policy 由产品负责人在控制台预建；
# 本脚本只核验、使用，不创建、不修改、不绑定任何 RAM 资源。
role_json="$("$CLI" ram get-role --role-name "$ROLE" 2>&1)" || fail_stop 'feedback 运行角色不存在或查询失败；请产品负责人在控制台预建后再试。'
role_arn="$(printf '%s' "$role_json" | jq -r '.Role.Arn // empty')"
trust_doc="$(printf '%s' "$role_json" | jq -r '.Role.AssumeRolePolicyDocument // empty')"
if [[ -z "$role_arn" || "$role_arn" == "null" || -z "$trust_doc" ]]; then
  fail_stop 'feedback 运行角色响应无法解析，已停止。'
fi
trust_json="$(printf '%s' "$trust_doc" | url_decode)"
if ! printf '%s' "$trust_json" | jq -e '
    (.Statement | type == "array" and length >= 1) and
    all(.Statement[];
      .Effect == "Allow"
      and .Action == "sts:AssumeRole"
      and ((.Principal | keys) == ["Service"])
      and ([.Principal.Service | if type == "array" then .[] else . end] == ["fc.aliyuncs.com"])
    )' >/dev/null; then
  fail_stop 'feedback 运行角色信任主体不是仅允许 FC 服务 AssumeRole，已停止。'
fi
printf 'ram_role=verified trust=fc-only\n'

policy_json="$("$CLI" ram get-policy --policy-name "$POLICY" --policy-type Custom 2>&1)" || fail_stop 'feedback 运行策略不存在或查询失败；请产品负责人在控制台预建后再试。'
if ! default_policy_version="$(printf '%s' "$policy_json" | jq -er '.Policy.DefaultVersion | select(type == "string")' 2>/dev/null)"; then
  fail_stop 'feedback 运行策略默认版本响应无法解析，已停止。'
fi
if [[ ! "$default_policy_version" =~ ^v[1-9][0-9]*$ ]]; then
  fail_stop 'feedback 运行策略默认版本格式无效，已停止。'
fi
policy_version_json="$("$CLI" ram get-policy-version --policy-name "$POLICY" --policy-type Custom --version-id "$default_policy_version" 2>&1)" || fail_stop 'feedback 运行策略默认版本不存在或查询失败，已停止。'
if ! returned_policy_version="$(printf '%s' "$policy_version_json" | jq -er '.PolicyVersion.VersionId | select(type == "string")' 2>/dev/null)" \
  || ! is_default_policy_version="$(printf '%s' "$policy_version_json" | jq -er '.PolicyVersion.IsDefaultVersion | select(type == "boolean")' 2>/dev/null)" \
  || ! policy_doc="$(printf '%s' "$policy_version_json" | jq -er '.PolicyVersion.PolicyDocument | select(type == "string" and length > 0)' 2>/dev/null)"; then
  fail_stop 'feedback 运行策略版本响应无法解析，已停止。'
fi
if [[ "$returned_policy_version" != "$default_policy_version" || "$is_default_policy_version" != "true" ]]; then
  fail_stop 'feedback 运行策略版本不是 GetPolicy 声明的默认版本，已停止。'
fi
policy_json_doc="$(printf '%s' "$policy_doc" | url_decode)"
bucket_resource="acs:oss:*:*:${FEEDBACK_BUCKET}"
write_resource="${bucket_resource}/feedback/*"
task_resource="${bucket_resource}/feedback/tasks/*"
review_resource="${bucket_resource}/feedback/reviews/*"
if ! printf '%s' "$policy_json_doc" | jq -e \
  --arg bucket "$bucket_resource" \
  --arg write "$write_resource" \
  --arg tasks "$task_resource" \
  --arg reviews "$review_resource" '
    (.Statement | type == "array" and length == 3) and
    ([.Statement[] | select(
      .Effect == "Allow"
      and ([.Action | if type == "array" then .[] else . end] == ["oss:PutObject"])
      and ([.Resource | if type == "array" then .[] else . end] == [$write])
      and (has("Condition") | not)
    )] | length == 1) and
    ([.Statement[] | select(
      .Effect == "Allow"
      and ([.Action | if type == "array" then .[] else . end] == ["oss:GetObject"])
      and (([.Resource | if type == "array" then .[] else . end] | sort) == ([$tasks, $reviews] | sort))
      and (has("Condition") | not)
    )] | length == 1) and
    ([.Statement[] | select(
      .Effect == "Allow"
      and ([.Action | if type == "array" then .[] else . end] == ["oss:ListObjects"])
      and ([.Resource | if type == "array" then .[] else . end] == [$bucket])
      and ((.Condition.StringLike["oss:Prefix"] | sort) == (["feedback/tasks/*", "feedback/reviews/*"] | sort))
    )] | length == 1)' >/dev/null; then
  fail_stop 'feedback 运行策略不符合追加写与老师任务/历史最小读取边界，已停止。'
fi
printf 'ram_policy=verified scope=feedback-write-and-teacher-review-read-only\n'

attach_json="$("$CLI" ram list-policies-for-role --role-name "$ROLE" 2>&1)" || fail_stop '无法读取角色已绑定策略列表，已停止。'
if ! printf '%s' "$attach_json" | jq -e --arg policy "$POLICY" '
    ([.Policies.Policy[]? | select(.PolicyType == "Custom") | .PolicyName] == [$policy]) and
    ([.Policies.Policy[]? | select(.PolicyType != "Custom")] | length == 0)' >/dev/null; then
  fail_stop 'feedback 运行角色绑定的策略不是恰好一个指定 custom policy（缺失或存在额外策略），已停止。'
fi
printf 'ram_policy_attachment=verified exact\n'

# ---- 全部只读核验通过后才允许写命令 ----
code_object="deploy/code/$package_sha.zip"
if [[ -n "${COURSEWARE_FEEDBACK_CODE_UPLOADER:-}" ]]; then
  "$COURSEWARE_FEEDBACK_CODE_UPLOADER" upload-code --package "$PACKAGE"
else
  CONTROL_DIR="$(mktemp -d /tmp/courseware-feedback-deploy.XXXXXX)"
  python3 -m pip install --disable-pip-version-check --no-input --target "$CONTROL_DIR" 'alibabacloud-oss-v2==1.3.2' >/dev/null
  PYTHONPATH="$CONTROL_DIR" OSS_ACCESS_KEY_ID="$ALIBABA_CLOUD_ACCESS_KEY_ID" OSS_ACCESS_KEY_SECRET="$ALIBABA_CLOUD_ACCESS_KEY_SECRET" \
    python3 "$MODULE_ROOT/deploy/upload_code.py" --package "$PACKAGE"
fi

runtime_config='{"command":["/code/bootstrap"],"port":9000,"healthCheckConfig":{"httpGetUrl":"/api/health","initialDelaySeconds":2,"periodSeconds":10,"timeoutSeconds":3,"failureThreshold":3,"successThreshold":1}}'
function_env=(
  "COURSEWARE_CLOUD_MODE=1"
  "COURSEWARE_FEEDBACK_OSS_BUCKET=$FEEDBACK_BUCKET"
  "COURSEWARE_OSS_REGION=$REGION"
  "COURSEWARE_OSS_ENDPOINT=https://oss-$REGION-internal.aliyuncs.com"
  "COURSEWARE_CORS_ORIGINS=$CORS_ORIGINS"
  "COURSEWARE_RATE_LIMIT_PER_CLIENT=$RATE_PER_CLIENT"
  "COURSEWARE_RATE_LIMIT_GLOBAL=$RATE_GLOBAL"
  "COURSEWARE_RATE_LIMIT_WINDOW=$RATE_WINDOW"
  "COURSEWARE_ACCESS_CODE=$COURSEWARE_ACCESS_CODE"
  "COURSEWARE_TEACHER_STORAGE_KEY=$TEACHER_STORAGE_KEY"
)
code_config=("ossBucketName=$COURSEWARE_OSS_BUCKET" "ossObjectName=$code_object")

"$CLI" fc update-function --region "$REGION" --function-name "$FUNCTION" \
  --code "${code_config[@]}" \
  --custom-runtime-config "$runtime_config" \
  --environment-variables "${function_env[@]}" \
  --role "$role_arn" --timeout 180 --memory-size 1024 --cpu "$CPU" --disk-size 512 \
  --instance-concurrency 8 --internet-access true >/dev/null
printf 'fc_function=updated\n'
"$CLI" fc put-concurrency-config --region "$REGION" --function-name "$FUNCTION" --reserved-concurrency 1 >/dev/null
printf 'fc_reserved_concurrency=1\n'
printf 'cloud_changes=applied\n'
