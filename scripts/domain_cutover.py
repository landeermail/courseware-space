#!/usr/bin/env python3
"""Render the备案完成后的切换步骤；当前版本只允许 dry-run。"""

from __future__ import annotations

import argparse
import re


DOMAIN = re.compile(r"^(?=.{4,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
BUCKET = re.compile(r"^courseware-space-[a-z0-9-]+$")
FUNCTION = re.compile(r"^courseware-space-[a-z0-9-]+$")


def cutover_steps(domain: str, icp_number: str, bucket: str, function: str) -> list[str]:
    domain = domain.strip().lower()
    icp_number = icp_number.strip()
    if not DOMAIN.fullmatch(domain):
        raise ValueError("domain 必须是已备案的裸域名，不含协议或路径")
    if not icp_number or len(icp_number) > 100:
        raise ValueError("icp-number 不能为空且不得超过 100 个字符")
    if not BUCKET.fullmatch(bucket):
        raise ValueError("oss-bucket 必须使用 courseware-space-* 前缀")
    if not FUNCTION.fullmatch(function):
        raise ValueError("fc-function 必须使用 courseware-space-* 前缀")
    static_host = f"courseware.{domain}"
    api_host = f"courseware-api.{domain}"
    return [
        f"1. 在 OSS bucket {bucket} 添加自定义域名 {static_host}（等待备案通过后执行）",
        f"2. 按 OSS 控制台给出的目标值，为 {static_host} 创建 CNAME；不使用脚本猜测目标值",
        f"3. 为 {static_host} 申请并绑定阿里云免费 SSL 证书，强制 HTTPS",
        f"4. 为 FC 函数 {function} 添加自定义域名 {api_host}，路由 /* 指向该函数",
        f"5. 按 FC 控制台给出的目标值，为 {api_host} 创建 CNAME，并绑定免费 SSL 证书",
        f"6. 将前端 API base 切换为 https://{api_host}，保留精确 CORS Origin https://{static_host}",
        f"7. 在网站页脚展示备案号“{icp_number}”并链接 https://beian.miit.gov.cn/",
        "8. 用真实桌面浏览器和 iPad 横屏走入口→课件→评价→自动返回全链路",
        "9. 验收 DNS、证书、CORS、403 闸门、反馈 OSS 写入后，再撤下 GitHub Pages 过渡入口",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="备案后域名切换计划（只读 dry-run）")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--icp-number", required=True)
    parser.add_argument("--oss-bucket", required=True)
    parser.add_argument("--fc-function", required=True)
    parser.add_argument("--dry-run", action="store_true", help="打印步骤，不修改任何云资源")
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("备案号未下，本脚本当前只允许 --dry-run")
    try:
        steps = cutover_steps(args.domain, args.icp_number, args.oss_bucket, args.fc_function)
    except ValueError as error:
        parser.error(str(error))
    print("mode=dry-run")
    for step in steps:
        print(step)
    print("cloud_changes=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
