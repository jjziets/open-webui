# SSO Setup Guide: WordPress + Open WebUI Integration

## Overview
This guide configures Single Sign-On (SSO) between WordPress (cryptolabs.co.za) and Open WebUI (webui.ai.cryptolabs.co.za) using trusted header authentication.

## Prerequisites
- SSH access: `ssh -i ~/.ssh/ubuntu_key -p 101 root@41.193.204.66`
- WordPress sFTP access: `sftp -P 22 crypthbfgw@cryptolabs.co.za`
- API Key: `sk-CPqwSu2GJcYjE0qrexd5rw`

## Step 1: Server Setup (GPU Server - 41.193.204.66)

### 1.1 Connect to Server
```bash
ssh -i ~/.ssh/ubuntu_key -p 101 root@41.193.204.66
```

### 1.2 Check Container Status
```bash
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'
```

### 1.3 Get Container IPs
```bash
WEBUI_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' open-webui)
LITELLM_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' litellm)
API_PROXY_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' api-proxy 2>/dev/null || echo "N/A")

echo "WebUI IP: $WEBUI_IP"
echo "LiteLLM IP: $LITELLM_IP"
echo "API Proxy IP: $API_PROXY_IP"
```

### 1.4 Install Nginx (if not already installed)
```bash
export DEBIAN_FRONTEND=noninteractive
apt-get update -y && apt-get install -y nginx certbot python3-certbot-nginx
systemctl enable --now nginx
```

### 1.5 Create Nginx Directories
```bash
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/nginx/snippets /var/www/letsencrypt
```

## Step 2: Configure Nginx Sites

### 2.1 WebUI Configuration
Create `/etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf`:

```nginx
map $http_upgrade $connection_upgrade {
  default upgrade;
  ''      close;
}

upstream open_webui_upstream {
  server WEBUI_IP:8080;  # Replace WEBUI_IP with actual IP from step 1.3
  keepalive 32;
}

server {
  listen 80;
  listen [::]:80;
  server_name webui.ai.cryptolabs.co.za;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name webui.ai.cryptolabs.co.za;

  ssl_certificate     /etc/letsencrypt/live/webui.ai.cryptolabs.co.za/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/webui.ai.cryptolabs.co.za/privkey.pem;

  client_max_body_size 100m;

  # COMMENT OUT this block to allow trusted header SSO from WordPress
  # location = /auth {
  #   return 302 /oauth/oidc/login;
  # }

  # WebSocket support
  location /ws/socket.io {
    proxy_pass http://open_webui_upstream;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
  }

  location / {
    proxy_pass http://open_webui_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Port $server_port;
    
    # Pass through trusted headers from WordPress
    proxy_set_header X-Webui-Email $http_x_webui_email;
    proxy_set_header X-Webui-Name $http_x_webui_name;
    proxy_set_header X-Webui-Groups $http_x_webui_groups;
    proxy_set_header X-User-Api-Key $http_x_user_api_key;
    
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
  }

  # ACME challenge
  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
}
```

### 2.2 API Configuration
Create `/etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf`:

```nginx
upstream litellm_upstream {
  server LITELLM_IP:4000;  # Replace LITELLM_IP with actual IP from step 1.3
  keepalive 16;
}

server {
  listen 80;
  listen [::]:80;
  server_name api.ai.cryptolabs.co.za;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name api.ai.cryptolabs.co.za;

  ssl_certificate     /etc/letsencrypt/live/api.ai.cryptolabs.co.za/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/api.ai.cryptolabs.co.za/privkey.pem;

  client_max_body_size 100m;
  
  proxy_read_timeout 3600s;
  proxy_send_timeout 3600s;
  proxy_connect_timeout 60s;

  location / {
    proxy_pass http://litellm_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Authorization $http_authorization;
    proxy_buffering off;
    proxy_cache off;
  }

  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
}
```

### 2.3 WPBM Configuration
Create `/etc/nginx/sites-available/wpbm.ai.cryptolabs.co.za.conf`:

```nginx
upstream wpbm_upstream {
  server 127.0.0.1:7777;
  keepalive 16;
}

server {
  listen 80;
  listen [::]:80;
  server_name wpbm.ai.cryptolabs.co.za;
  return 301 https://$host$request_uri;
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name wpbm.ai.cryptolabs.co.za;

  ssl_certificate     /etc/letsencrypt/live/wpbm.ai.cryptolabs.co.za/fullchain.pem;
  ssl_certificate_key /etc/letsencrypt/live/wpbm.ai.cryptolabs.co.za/privkey.pem;

  client_max_body_size 100m;

  location / {
    proxy_pass http://wpbm_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
  }

  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
}
```

### 2.4 Replace Container IPs in Configs
```bash
# Get the actual IPs
WEBUI_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' open-webui)
LITELLM_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' litellm)

# Replace in configs
sed -i "s/WEBUI_IP/$WEBUI_IP/g" /etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf
sed -i "s/LITELLM_IP/$LITELLM_IP/g" /etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf
```

### 2.5 Enable Sites and Redirects
```bash
# Enable sites
ln -sf /etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/wpbm.ai.cryptolabs.co.za.conf /etc/nginx/sites-enabled/

# Copy redirect snippet
mkdir -p /etc/nginx/snippets
cat > /etc/nginx/snippets/cryptolabs.co.za-redirects.conf << 'EOF'
location = /ai-chat {
  return 301 https://webui.ai.cryptolabs.co.za/auth?redirect=%2F;
}

location = /ai-chat/ {
  return 301 https://webui.ai.cryptolabs.co.za/auth?redirect=%2F;
}
EOF

# Test and reload
nginx -t && systemctl reload nginx
```

## Step 3: Configure SSL Certificates

```bash
# Stop any existing services on port 80/443
docker stop caddy 2>/dev/null || true
docker rm caddy 2>/dev/null || true

# Get certificates
certbot --nginx -d webui.ai.cryptolabs.co.za -d wpbm.ai.cryptolabs.co.za -d api.ai.cryptolabs.co.za
```

## Step 4: Configure Open WebUI for Trusted Header SSO

### 4.1 Update Open WebUI Environment
```bash
# Stop the container
docker stop open-webui

# Start with trusted header authentication enabled
docker run -d \
  --name open-webui \
  --restart always \
  -e WEBUI_URL=https://webui.ai.cryptolabs.co.za \
  -e WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Webui-Email \
  -e WEBUI_AUTH_TRUSTED_NAME_HEADER=X-Webui-Name \
  -e WEBUI_AUTH_TRUSTED_GROUPS_HEADER=X-Webui-Groups \
  -e WEBUI_AUTH_SIGNOUT_REDIRECT_URL=https://www.cryptolabs.co.za/ai-chat/ \
  -e ENABLE_SIGNUP=false \
  -e DEFAULT_USER_ROLE=user \
  -v open-webui:/app/backend/data \
  --network open-webui-network \
  ghcr.io/open-webui/open-webui:main
```

*Note: Adjust the docker run command based on your existing container configuration*

### 4.2 Verify Configuration
```bash
# Check if trusted header is enabled
curl -sS https://webui.ai.cryptolabs.co.za/api/config | jq '.features.auth_trusted_header'
```

## Step 5: Test Services

### 5.1 Test WebUI
```bash
curl -I https://webui.ai.cryptolabs.co.za/
```

### 5.2 Test API
```bash
export API_KEY='sk-CPqwSu2GJcYjE0qrexd5rw'
curl https://api.ai.cryptolabs.co.za/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "qwen3-coder-30b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 5.3 Test WPBM
```bash
curl -I https://wpbm.ai.cryptolabs.co.za/
```

## Step 6: WordPress Configuration

### 6.1 Update WordPress Nginx Configuration
On the WordPress server, ensure the Nginx configuration includes proper proxy headers for SSO.

Add to the WordPress Nginx server block:

```nginx
# In the location block that proxies to PHP/WordPress
location /ai-chat-proxy {
  # Get WordPress user info (this requires custom WordPress code)
  set $wp_user_email "";
  set $wp_user_name "";
  
  # Proxy to WebUI with authentication headers
  proxy_pass https://webui.ai.cryptolabs.co.za/;
  proxy_set_header X-Webui-Email $wp_user_email;
  proxy_set_header X-Webui-Name $wp_user_name;
  proxy_set_header X-Webui-Groups "users";
  
  # Standard proxy headers
  proxy_set_header Host webui.ai.cryptolabs.co.za;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
}
```

### 6.2 Configure Cryptolabs AI Gateway Plugin

1. Access WordPress admin panel
2. Navigate to Cryptolabs AI Gateway settings
3. Configure:
   - API Endpoint: `https://api.ai.cryptolabs.co.za/v1`
   - API Key: `sk-CPqwSu2GJcYjE0qrexd5rw`
   - Enable SSO: Yes
   - SSO Type: Trusted Header
   - WebUI URL: `https://webui.ai.cryptolabs.co.za`

## Troubleshooting

### Check Services
```bash
# Check all listeners
ss -ltnp | grep -E ':80|:443|:8080|:4000|:7777'

# Check container logs
docker logs --tail=100 open-webui
docker logs --tail=100 litellm

# Check Nginx logs
tail -f /var/log/nginx/error.log
```

### Common Issues

1. **502 Bad Gateway**: Container IP changed, update Nginx upstream
2. **SSL Error**: Run certbot again
3. **SSO Not Working**: Verify trusted headers are passed and WebUI env vars are set
4. **API Connection Refused**: Check LiteLLM container is running and port is correct

## Maintenance

### Certificate Renewal
```bash
# Test renewal
certbot renew --dry-run

# Auto-renewal is handled by certbot systemd timer
systemctl status certbot.timer
```

### Update Container IPs After Restart
```bash
# Script to update IPs
cat > /usr/local/bin/update-nginx-upstreams.sh << 'EOF'
#!/bin/bash
WEBUI_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' open-webui)
LITELLM_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' litellm)

sed -i "s/server [0-9.]*:8080/server $WEBUI_IP:8080/g" /etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf
sed -i "s/server [0-9.]*:4000/server $LITELLM_IP:4000/g" /etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf

nginx -t && systemctl reload nginx
EOF

chmod +x /usr/local/bin/update-nginx-upstreams.sh
```
