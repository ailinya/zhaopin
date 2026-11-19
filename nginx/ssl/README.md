# SSL 证书目录

**生产环境必须**：
1. 把正式的 SSL 证书和私钥放到这个目录
2. 文件名要与 `nginx.conf` 中 `ssl_certificate` / `ssl_certificate_key` 配置一致
3. **不要**把真实证书提交到 git（已在 `.gitignore` 中屏蔽 `*.pem` 和 `*.key`）

## 自签名证书（仅用于本地开发）

```bash
# 生成自签名证书（365 天）
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout localhost.key \
  -out localhost.pem \
  -subj "/C=CN/ST=Beijing/L=Beijing/O=Dev/OU=Dev/CN=localhost"
```

## Let's Encrypt（生产推荐）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 自动续期（cron）
sudo certbot renew --dry-run
```

## 文件命名约定

| 文件 | 用途 |
|---|---|
| `your-domain.pem` | 公钥证书 |
| `your-domain.key` | 私钥 |
| `dhparam.pem` | Diffie-Hellman 参数（可选，增强安全）|

## 修改 nginx.conf

把 `nginx.conf` 中的占位符替换为你的实际配置：

```nginx
server_name your-domain.com;  →  server_name interview.example.com;
ssl_certificate     /etc/nginx/ssl/your-domain.pem;      →  /etc/nginx/ssl/interview.example.com.pem;
ssl_certificate_key /etc/nginx/ssl/your-domain.key;      →  /etc/nginx/ssl/interview.example.com.key;
```