# 部署说明

## 1. 服务器

- 建议地区：首尔 / 东京 / 新加坡（Binance 行情走 `data-api.binance.vision`，不受地区限制；KRX 和 KakaoTalk 在首尔延迟最低）
- 配置：2 核 4GB 内存、50GB 硬盘，Ubuntu 22.04 / 24.04
- 安装 Docker：

```bash
curl -fsSL https://get.docker.com | sh
```

## 2. 启动

```bash
git clone https://github.com/jinmin888/stocks.git
cd stocks
cp .env.example .env
```

编辑 `.env`，至少填写：

| 变量 | 说明 |
|---|---|
| `APP_PASSWORD` | 网站登录密码（账号默认 `admin`，可用 `APP_USERNAME` 修改） |
| `SECRET_KEY` | 随机长字符串，用于签名登录 Cookie：`python3 -c "import secrets;print(secrets.token_hex(32))"` |
| `PUBLIC_URL` | 网站对外地址，如 `http://服务器IP:8000`；KakaoTalk 消息里的链接和授权回调都会用到 |
| `KRX_ID` / `KRX_PW` | 韩国交易所数据平台账号（韩国股市全市场 / 指数扫描） |
| `KAKAO_REST_API_KEY` | 见下文「KakaoTalk」 |

```bash
docker compose up -d --build
```

打开 `http://服务器IP:8000` 登录。数据（数据库、行情缓存）保存在 `./data`，升级或重建容器不会丢失。

防火墙需放行 8000 端口（启用 HTTPS 后改为 80 / 443）。

## 3. KakaoTalk 通知

1. 打开 [Kakao Developers](https://developers.kakao.com) → 내 애플리케이션 → 애플리케이션 추가하기
2. 앱 키 → 复制 **REST API 키**，填到 `.env` 的 `KAKAO_REST_API_KEY`
3. 플랫폼 → Web → 사이트 도메인：登记 `PUBLIC_URL`（消息中的链接必须是登记过的域名）
4. 카카오 로그인 → 활성화 설정 ON；Redirect URI 登记：`PUBLIC_URL` + `/api/kakao/callback`
   （网站「设置」页也会显示这个地址）
5. 동의항목 → 「카카오톡 메시지 전송（talk_message）」设为可选同意或必须同意
6. 若在 보안 页启用了 Client Secret，把它填到 `KAKAO_CLIENT_SECRET`
7. `docker compose up -d` 重启，在网站「设置」页点「连接 KakaoTalk」授权，再点「发送测试消息」确认

Kakao 后台的菜单名称可能随版本变化，以实际页面为准。如果 Kakao 不接受 IP 形式的地址，需要先配置域名（见下一节）。

授权约 2 个月有效；只要定时任务在运行，程序发送消息时会自动续期。服务器停机超过 2 个月需要重新连接。

## 4. 域名与 HTTPS（可选）

1. 域名 A 记录指向服务器 IP
2. `.env` 中设置：

```
DOMAIN=screener.example.com
PUBLIC_URL=https://screener.example.com
COOKIE_SECURE=1
```

3. 启动带 Caddy 的配置（自动申请 Let's Encrypt 证书）：

```bash
docker compose --profile https up -d --build
```

4. 在 Kakao Developers 中把站点域名和 Redirect URI 改成 https 地址
5. 可把 `docker-compose.yml` 中 app 的端口改为 `"127.0.0.1:8000:8000"`，只允许通过 HTTPS 访问

## 5. 升级

```bash
git pull
docker compose up -d --build
```

## 6. 常见问题

- **A 股扫描慢 / 部分失败**：东方财富会对频繁请求限流。失败的标的会在 5 分钟后自动重试一次（`RETRY_WAIT`），结果页会列出仍未取到数据的标的。首次运行需要下载约 2 年历史，之后只增量更新。
- **韩国股市提示需要 KRX 账号**：检查 `.env` 中的 `KRX_ID` / `KRX_PW`，并确认能用该账号登录 data.krx.co.kr。
- **查看日志**：`docker compose logs -f app`
