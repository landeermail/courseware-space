# 待裁决清单

本文件只保留仍需处理或达到触发条件后必须处理的事项。已解除故障和既有实施过程见 `PROGRESS.md`、ADR 与 Git 历史。

## 临时 Root AccessKey 云端删除

- **现状**：2026-08-13 为修正 OSS Bucket Policy 临时创建了一把 Root AccessKey；本机钥匙串副本已删除，生产部署已恢复使用最小权限 `courseware-space-deployer`。
- **待办**：产品负责人在阿里云控制台删除该临时 Root AccessKey。未确认云端删除前，不得把本机副本删除写成凭证已经完全收口。
- **影响**：不阻塞静态课件和评价使用；会阻塞任何宣称“临时 Root 凭证已彻底清理”的结论。

## 备案后域名切换与 Pages 过渡入口

- **现状**：`deploy/domain_cutover.py` 仅支持 `--dry-run`；随机 GitHub Pages 入口仍是备案等待期的过渡方案。
- **触发条件**：备案号、DNS、SSL 与自定义域名均可用后。
- **待裁决**：按 `deploy/domain-cutover-runbook.md` 完成新域名桌面与 iPad 横屏闭环，再决定保留还是撤下随机 Pages 入口。脚本不得替产品负责人自动删除旧入口。
