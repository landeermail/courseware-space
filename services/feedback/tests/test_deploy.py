from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_ROOT = ROOT / "services" / "feedback"
DEPLOY_SCRIPT = MODULE_ROOT / "deploy" / "deploy.sh"
BUILD_SCRIPT = MODULE_ROOT / "deploy" / "build_package.sh"
STRONG_CODE = "a1" * 24
TEACHER_STORAGE_KEY = "c3" * 32
BUCKET_SUFFIX = "10794778"
FEEDBACK_BUCKET = f"courseware-space-private-{BUCKET_SUFFIX}"
ROLE = "courseware-space-fc-feedback-role"
POLICY = "courseware-space-fc-feedback-write"
ACCOUNT = "123456789012"
EXPECTED_RESOURCE = f"acs:oss:*:*:{FEEDBACK_BUCKET}/feedback/*"
BUCKET_RESOURCE = f"acs:oss:*:*:{FEEDBACK_BUCKET}"
TASK_RESOURCE = f"{BUCKET_RESOURCE}/feedback/tasks/*"
REVIEW_RESOURCE = f"{BUCKET_RESOURCE}/feedback/reviews/*"

IDENTITY_RAM_USER = json.dumps({"AccountId": ACCOUNT, "Arn": f"acs:ram::{ACCOUNT}:user/deployer"})
IDENTITY_ROOT = json.dumps({"AccountId": ACCOUNT, "Arn": f"acs:ram::{ACCOUNT}:root"})

TRUST_FC_ONLY = {
    "Version": "1",
    "Statement": [
        {"Effect": "Allow", "Principal": {"Service": ["fc.aliyuncs.com"]}, "Action": "sts:AssumeRole"}
    ],
}
POLICY_FEEDBACK_ONLY = {
    "Version": "1",
    "Statement": [
        {"Effect": "Allow", "Action": ["oss:PutObject"], "Resource": [EXPECTED_RESOURCE]},
        {
            "Effect": "Allow",
            "Action": ["oss:GetObject"],
            "Resource": [TASK_RESOURCE, REVIEW_RESOURCE],
        },
        {
            "Effect": "Allow",
            "Action": ["oss:ListObjects"],
            "Resource": [BUCKET_RESOURCE],
            "Condition": {
                "StringLike": {
                    "oss:Prefix": ["feedback/tasks/*", "feedback/reviews/*"]
                }
            },
        },
    ],
}
ATTACH_EXACT = {
    "Policies": {"Policy": [{"PolicyName": POLICY, "PolicyType": "Custom"}]}
}

WRITE_MARKERS = (
    "upload-code",
    "update-function",
    "put-concurrency-config",
    "create-function",
    "create-trigger",
    "create-role",
    "create-policy",
    "attach-policy-to-role",
)


def role_response(trust: dict[str, object] | None = None) -> str:
    return json.dumps(
        {
            "Role": {
                "Arn": f"acs:ram::{ACCOUNT}:role/{ROLE}",
                "AssumeRolePolicyDocument": json.dumps(trust or TRUST_FC_ONLY),
            }
        }
    )


def policy_response(
    default_version: str = "v1",
    deprecated_document: dict[str, object] | None = None,
) -> str:
    policy: dict[str, object] = {
        "PolicyName": POLICY,
        "PolicyType": "Custom",
        "DefaultVersion": default_version,
    }
    if deprecated_document is not None:
        policy["PolicyDocument"] = json.dumps(deprecated_document)
    return json.dumps({"Policy": policy})


def policy_version_response(
    document: dict[str, object] | None = None,
    version_id: str = "v1",
    is_default: bool = True,
) -> str:
    return json.dumps(
        {
            "PolicyVersion": {
                "VersionId": version_id,
                "IsDefaultVersion": is_default,
                "PolicyDocument": json.dumps(document or POLICY_FEEDBACK_ONLY),
            }
        }
    )


def precise_responses() -> list[tuple[str, str | None, int]]:
    return [
        ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
        ("get-role", role_response(), 0),
        ("get-policy-version", policy_version_response(), 0),
        ("get-policy", policy_response(), 0),
        ("list-policies-for-role", json.dumps(ATTACH_EXACT), 0),
    ]


class FeedbackOnlyDeployTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = tempfile.TemporaryDirectory()
        self.work = Path(self._temporary.name)
        self.cli_log = self.work / "fake-cli.log"
        self.fake_cli = self.work / "aliyun-fake"
        self.fake_uploader = self.work / "uploader-fake"
        self.fake_uploader.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$*" >> "' + str(self.cli_log) + '"\n',
            encoding="utf-8",
        )
        self.fake_uploader.chmod(self.fake_uploader.stat().st_mode | stat.S_IXUSR)
        self.package = self.work / "feedback.zip"
        with zipfile.ZipFile(self.package, "w") as archive:
            archive.writestr("bootstrap", "#!/bin/sh\n")
            self.write_runtime_whitelist(archive)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    @staticmethod
    def write_runtime_whitelist(archive: zipfile.ZipFile) -> None:
        for path in (
            "services/__init__.py",
            "services/feedback/__init__.py",
            "services/feedback/access_control.py",
            "services/feedback/app.py",
            "services/feedback/review_workspace.py",
            "services/feedback/schema/__init__.py",
            "services/feedback/schema/validate_feedback.py",
            "services/feedback/service.py",
        ):
            archive.writestr(path, "# feedback runtime\n")

    def write_cli(self, responses: list[tuple[str, str | None, int]]) -> None:
        lines = [
            "#!/bin/sh",
            'printf "%s\\n" "$*" >> "' + str(self.cli_log) + '"',
            'case "$*" in',
        ]
        for index, (match, content, code) in enumerate(responses):
            body = f"  *{match}*) "
            if content is not None:
                response_file = self.work / f"resp-{index}.json"
                response_file.write_text(content, encoding="utf-8")
                body += f'cat "{response_file}"; '
            body += f"exit {code} ;;"
            lines.append(body)
        lines.append("esac")
        lines.append("exit 0")
        self.fake_cli.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.fake_cli.chmod(self.fake_cli.stat().st_mode | stat.S_IXUSR)

    def base_env(self) -> dict[str, str]:
        self.write_cli([])
        return {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "COURSEWARE_ACCESS_CODE": STRONG_CODE,
            "COURSEWARE_TEACHER_STORAGE_KEY": TEACHER_STORAGE_KEY,
            "COURSEWARE_FEEDBACK_OSS_BUCKET": FEEDBACK_BUCKET,
            "ALIYUN_CLI": str(self.fake_cli),
            "COURSEWARE_FEEDBACK_PACKAGE": str(self.package),
        }

    def apply_env(self) -> dict[str, str]:
        env = self.base_env()
        env["ALIBABA_CLOUD_ACCESS_KEY_ID"] = "fake-id"
        env["ALIBABA_CLOUD_ACCESS_KEY_SECRET"] = "fake-secret"
        env["COURSEWARE_OSS_BUCKET"] = "courseware-space-demo-1"
        env["COURSEWARE_FEEDBACK_CODE_UPLOADER"] = str(self.fake_uploader)
        return env

    def run_deploy(self, env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DEPLOY_SCRIPT), *args],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def run_audit(self, zip_path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(BUILD_SCRIPT), "--audit-only", str(zip_path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def cli_calls(self) -> list[str]:
        if not self.cli_log.is_file():
            return []
        return [line for line in self.cli_log.read_text(encoding="utf-8").splitlines() if line.strip()]

    def assert_no_writes(self) -> None:
        for call in self.cli_calls():
            for forbidden in WRITE_MARKERS:
                self.assertNotIn(forbidden, call)

    # ---- 默认 dry-run 与前置校验 ----

    def test_default_is_dry_run_with_zero_cloud_calls(self) -> None:
        result = self.run_deploy(self.base_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mode=dry-run", result.stdout)
        self.assertIn("cloud_changes=0", result.stdout)
        self.assertEqual(self.cli_calls(), [])

    def test_dry_run_plan_is_masked_and_keeps_only_feedback_prefix(self) -> None:
        result = self.run_deploy(self.base_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("policy_actions=oss:PutObject,oss:GetObject,oss:ListObjects", result.stdout)
        self.assertIn("policy_write_resource=acs:oss:*:*:courseware-space-private-***/feedback/*", result.stdout)
        self.assertIn("policy_read_resources=acs:oss:*:*:courseware-space-private-***/feedback/tasks/*,acs:oss:*:*:courseware-space-private-***/feedback/reviews/*", result.stdout)
        self.assertIn("policy_list_prefixes=feedback/tasks/*,feedback/reviews/*", result.stdout)
        self.assertIn("policy_staging_grants=0", result.stdout)
        self.assertIn("kimi_env_vars=0", result.stdout)
        self.assertIn("trigger_url=preserved-not-printed", result.stdout)
        self.assertNotIn(BUCKET_SUFFIX, result.stdout)
        self.assertNotIn(STRONG_CODE, result.stdout)
        self.assertNotIn("staging/*", result.stdout)
        self.assertNotIn("https://", result.stdout)
        self.assertNotIn("KIMI_API_KEY", result.stdout)

    def test_non_private_feedback_bucket_is_rejected(self) -> None:
        env = self.base_env()
        env["COURSEWARE_FEEDBACK_OSS_BUCKET"] = "courseware-space-demo-123"
        result = self.run_deploy(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("courseware-space-private-*", result.stderr)
        self.assertEqual(self.cli_calls(), [])

    def test_kimi_environment_variable_is_rejected(self) -> None:
        env = self.base_env()
        env["KIMI_API_KEY"] = "sk-kimi-fake"
        result = self.run_deploy(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Kimi", result.stderr)
        self.assertEqual(self.cli_calls(), [])

    def test_missing_access_code_is_rejected(self) -> None:
        env = self.base_env()
        del env["COURSEWARE_ACCESS_CODE"]
        result = self.run_deploy(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("COURSEWARE_ACCESS_CODE", result.stderr)
        self.assertEqual(self.cli_calls(), [])

    def test_weak_access_code_is_rejected(self) -> None:
        env = self.base_env()
        env["COURSEWARE_ACCESS_CODE"] = "weak"
        result = self.run_deploy(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.cli_calls(), [])

    def test_missing_teacher_storage_key_is_rejected(self) -> None:
        env = self.base_env()
        del env["COURSEWARE_TEACHER_STORAGE_KEY"]
        result = self.run_deploy(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TEACHER_STORAGE_KEY", result.stderr)
        self.assertEqual(self.cli_calls(), [])

    def test_apply_is_explicit_and_still_refuses_without_credentials(self) -> None:
        default_result = self.run_deploy(self.base_env())
        self.assertEqual(default_result.returncode, 0, default_result.stderr)
        self.assertIn("cloud_changes=0", default_result.stdout)

        apply_result = self.run_deploy(self.base_env(), "--apply")
        self.assertNotEqual(apply_result.returncode, 0)
        self.assertIn("ALIBABA_CLOUD_ACCESS_KEY_ID", apply_result.stderr)
        self.assertEqual(self.cli_calls(), [])

    def test_malicious_package_is_rejected_before_any_success_claim(self) -> None:
        malicious = self.work / "malicious.zip"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("services/feedback/app.py", 'import os\nkey = os.environ["KIMI_API_KEY"]\n')
            archive.writestr("server/kimi_client.py", "# model client\n")
        env = self.base_env()
        env["COURSEWARE_FEEDBACK_PACKAGE"] = str(malicious)
        result = self.run_deploy(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("cloud_changes=0", result.stdout)
        self.assertNotIn("package_kimi_refs=0", result.stdout)
        self.assertEqual(self.cli_calls(), [])

    # ---- 任务 1：部署入口拒绝主账号 ----

    def test_root_identity_is_rejected_before_any_write(self) -> None:
        env = self.apply_env()
        self.write_cli([("GetCallerIdentity", IDENTITY_ROOT, 0)])
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("主账号", result.stderr)
        self.assertNotIn(ACCOUNT, result.stderr)
        self.assertNotIn(ACCOUNT, result.stdout)
        self.assertEqual(len(self.cli_calls()), 1)
        self.assertIn("GetCallerIdentity", self.cli_calls()[0])
        self.assert_no_writes()

    def test_identity_query_failure_is_rejected(self) -> None:
        env = self.apply_env()
        self.write_cli([("GetCallerIdentity", "NoSuchEntity error", 1)])
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(ACCOUNT, result.stderr)
        self.assert_no_writes()

    def test_identity_unparseable_is_rejected(self) -> None:
        env = self.apply_env()
        self.write_cli([("GetCallerIdentity", "this-is-not-json", 0)])
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_identity_blank_is_rejected(self) -> None:
        env = self.apply_env()
        self.write_cli([("GetCallerIdentity", "{}", 0)])
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_ram_user_proceeds_to_readonly_verification(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", "EntityNotExist.Role", 1),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GetCallerIdentity", self.cli_calls()[0])
        self.assertIn("get-role", self.cli_calls()[1])
        self.assert_no_writes()

    # ---- 任务 2：预创建 role/policy 精确只读核验 ----

    def test_apply_fails_when_role_missing(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", "EntityNotExist.Role", 1),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_policy_missing(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy", "EntityNotExist.Policy", 1),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_default_policy_version_is_missing(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy", json.dumps({"Policy": {"PolicyName": POLICY, "PolicyType": "Custom"}}), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_default_policy_version_query_fails(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", "EntityNotExist.Policy.Version", 1),
                ("get-policy", policy_response(), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("get-policy-version", self.cli_calls()[-1])
        self.assert_no_writes()

    def test_apply_fails_when_policy_version_is_not_the_declared_default(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", policy_version_response(version_id="v2", is_default=False), 0),
                ("get-policy", policy_response(default_version="v1"), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_trust_is_not_fc_only(self) -> None:
        trust = {
            "Version": "1",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": ["fc.aliyuncs.com"], "AWS": [f"acs:ram::{ACCOUNT}:user/other"]},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(trust), 0),
                ("get-policy-version", policy_version_response(), 0),
                ("get-policy", policy_response(), 0),
                ("list-policies-for-role", json.dumps(ATTACH_EXACT), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_feedback_prefix_is_widened(self) -> None:
        document = {
            "Version": "1",
            "Statement": [
                {"Effect": "Allow", "Action": ["oss:PutObject"], "Resource": [f"acs:oss:*:*:{FEEDBACK_BUCKET}/*"]}
            ],
        }
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", policy_version_response(document), 0),
                ("get-policy", policy_response(deprecated_document=POLICY_FEEDBACK_ONLY), 0),
                ("list-policies-for-role", json.dumps(ATTACH_EXACT), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_staging_grant_is_added(self) -> None:
        document = {
            "Version": "1",
            "Statement": [
                {"Effect": "Allow", "Action": ["oss:PutObject"], "Resource": [EXPECTED_RESOURCE]},
                {
                    "Effect": "Allow",
                    "Action": ["oss:PutObject"],
                    "Resource": ["acs:oss:*:*:courseware-space-demo-1/staging/*"],
                },
            ],
        }
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", policy_version_response(document), 0),
                ("get-policy", policy_response(), 0),
                ("list-policies-for-role", json.dumps(ATTACH_EXACT), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_extra_action_is_added(self) -> None:
        document = {
            "Version": "1",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["oss:PutObject", "oss:PutObjectAcl"],
                    "Resource": [EXPECTED_RESOURCE],
                }
            ],
        }
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", policy_version_response(document), 0),
                ("get-policy", policy_response(), 0),
                ("list-policies-for-role", json.dumps(ATTACH_EXACT), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_extra_policy_is_attached(self) -> None:
        attached = {
            "Policies": {
                "Policy": [
                    {"PolicyName": POLICY, "PolicyType": "Custom"},
                    {"PolicyName": "courseware-space-extra-policy", "PolicyType": "Custom"},
                ]
            }
        }
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", policy_version_response(), 0),
                ("get-policy", policy_response(), 0),
                ("list-policies-for-role", json.dumps(attached), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_apply_fails_when_policy_attachment_is_missing(self) -> None:
        env = self.apply_env()
        self.write_cli(
            [
                ("GetCallerIdentity", IDENTITY_RAM_USER, 0),
                ("get-role", role_response(), 0),
                ("get-policy-version", policy_version_response(), 0),
                ("get-policy", policy_response(), 0),
                ("list-policies-for-role", json.dumps({"Policies": {"Policy": []}}), 0),
            ]
        )
        result = self.run_deploy(env, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assert_no_writes()

    def test_precise_config_reaches_first_allowed_write_in_order(self) -> None:
        env = self.apply_env()
        self.write_cli(precise_responses())
        result = self.run_deploy(env, "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ram_role=verified trust=fc-only", result.stdout)
        self.assertIn("ram_policy=verified scope=feedback-write-and-teacher-review-read-only", result.stdout)
        self.assertIn("ram_policy_attachment=verified exact", result.stdout)
        self.assertIn("cloud_changes=applied", result.stdout)
        calls = self.cli_calls()
        self.assertEqual(len(calls), 8)
        self.assertIn("GetCallerIdentity", calls[0])
        self.assertIn("get-role", calls[1])
        self.assertIn("get-policy", calls[2])
        self.assertIn("get-policy-version", calls[3])
        self.assertIn("--version-id v1", calls[3])
        self.assertIn("list-policies-for-role", calls[4])
        self.assertIn("upload-code", calls[5])
        self.assertIn("update-function", calls[6])
        self.assertIn("put-concurrency-config", calls[7])
        for call in calls:
            for forbidden in ("create-role", "create-policy", "attach-policy-to-role"):
                self.assertNotIn(forbidden, call)

    # ---- 包审计 ----

    def test_package_audit_accepts_whitelist_zip(self) -> None:
        clean = self.work / "clean.zip"
        with zipfile.ZipFile(clean, "w") as archive:
            archive.writestr("bootstrap", "#!/bin/sh\n")
            self.write_runtime_whitelist(archive)
            archive.writestr("python/alibabacloud_oss_v2/__init__.py", "# sdk\n")
        result = self.run_audit(clean)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("required_files=9 unexpected_files=0", result.stdout)

    def test_package_audit_rejects_non_runtime_feedback_files(self) -> None:
        dirty = self.work / "dirty-extra.zip"
        with zipfile.ZipFile(dirty, "w") as archive:
            archive.writestr("bootstrap", "#!/bin/sh\n")
            self.write_runtime_whitelist(archive)
            archive.writestr("services/feedback/history/review.json", "{}\n")
        result = self.run_audit(dirty)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("白名单外", result.stderr)

    def test_package_audit_rejects_forbidden_file_names(self) -> None:
        dirty = self.work / "dirty.zip"
        with zipfile.ZipFile(dirty, "w") as archive:
            archive.writestr("services/feedback/app.py", "# feedback\n")
            archive.writestr("server/kimi_client.py", "# model client\n")
        result = self.run_audit(dirty)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kimi_client.py", result.stderr)

    def test_package_audit_rejects_kimi_content(self) -> None:
        dirty = self.work / "dirty-content.zip"
        with zipfile.ZipFile(dirty, "w") as archive:
            archive.writestr("services/feedback/app.py", 'import os\nkey = os.environ["KIMI_API_KEY"]\n')
        result = self.run_audit(dirty)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
