# 备案后域名切换 Runbook

本文件只用于备案通过后的切换准备。备案号下来前，不绑定域名、不修改 DNS、不申请面向该域名的生产证书。当前脚本只支持 `--dry-run`，因此不会改动阿里云资源。

## 领导需要填的四项

```bash
export COURSEWARE_DOMAIN='已备案的裸域名'
export COURSEWARE_ICP_NUMBER='备案号'
export COURSEWARE_SITE_OSS_BUCKET='承载静态站点的 courseware-space-* bucket'
export COURSEWARE_FC_FUNCTION='当前 feedback-only FC function 名'
```

先预演并逐行核对：

```bash
python3 scripts/domain_cutover.py \
  --domain "$COURSEWARE_DOMAIN" \
  --icp-number "$COURSEWARE_ICP_NUMBER" \
  --oss-bucket "$COURSEWARE_SITE_OSS_BUCKET" \
  --fc-function "$COURSEWARE_FC_FUNCTION" \
  --dry-run
```

## 备案通过后的人工切换顺序

1. 在 OSS 为 `courseware.<域名>` 添加自定义域名。只采用控制台实际返回的 CNAME 目标值，不从 bucket 名猜测。
2. 在 DNS 创建该 CNAME，等待解析生效；保留 GitHub Pages 过渡入口作为回退。
3. 在阿里云申请免费 SSL 证书，绑定到 OSS 自定义域名并强制 HTTPS。
4. 在 FC 为 `courseware-api.<域名>` 添加自定义域名，`/*` 路由到当前 feedback-only function。
5. 按 FC 控制台返回值创建 API CNAME，并绑定免费 SSL 证书。
6. 把前端 API base 改为 API 自定义域名，并把服务端 CORS 精确加入静态站点 Origin；不要使用 `*`。
7. 在所有对外页面页脚展示备案号，并链接工信部备案查询站点。
8. 先只读验证无码/错码为 403、老师原凭证读取 `GET /api/reviews` 为 200、生成路由为 404；不得为了域名冒烟测试提交或覆盖老师评价。
9. 用真实桌面浏览器和 iPad 横屏完成“原长期入口→课件→评价入口→历史评价”的只读链路，检查跨域、控制台、404、横向溢出和触控。只有产品负责人另行授权时才实际提交一版评价。
10. 上述证据全部通过后，才决定是否撤下随机 GitHub Pages 过渡页。该决定仍保留在 `BLOCKED.md`，不由本脚本自动执行。

## 回退

- 不删除旧 Pages 入口和 FC 默认触发器，先恢复前端 API base 与 CORS。
- 删除或暂停有问题的 CNAME，而不是删除 OSS 数据或 FC 函数。
- SSL、DNS 或 CORS 任一项未通过时，不宣布切换完成。
