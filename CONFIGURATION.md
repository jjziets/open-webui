# Open WebUI Configuration

This file documents all configuration needed to recreate the Open WebUI deployment from scratch.

## Docker Image

**Repository**: jjziets/open-webui  
**Registry**: Docker Hub  
**Tags**: latest, main, {commit-sha}

## Environment Variables (Required)

These are configured in `cryptolabs-ai-platform/services/docker-compose.yml`:

### Core Settings
```env
WEBUI_URL=https://webui.ai.cryptolabs.co.za
OPENAI_API_BASE_URL=http://litellm:4000/v1
DEFAULT_USER_ROLE=user
ENABLE_ADMIN_EXPORT=true
```

### SSO Configuration (Trusted Headers)
```env
# WordPress SSO integration via nginx auth_request
WEBUI_AUTH_TRUSTED_EMAIL_HEADER=X-Webui-Email
WEBUI_AUTH_TRUSTED_NAME_HEADER=X-Webui-Name
WEBUI_AUTH_TRUSTED_API_KEY_HEADER=X-User-Api-Key

# Disable other auth methods (SSO only)
ENABLE_SIGNUP=false
ENABLE_LOGIN_FORM=false
ENABLE_OAUTH_SIGNUP=false
```

### LiteLLM Integration
```env
WEBUI_LITELLM_DEFAULT_URL=https://api.ai.cryptolabs.co.za/v1
WEBUI_LITELLM_DEFAULT_MODEL=qwen3-coder-30b
```

## Port Mapping

```yaml
ports:
  - "8080:8080"
```

**Why**: nginx (runs on host) needs to access Open WebUI via localhost:8080

## Volume Mounts

```yaml
volumes:
  - /var/lib/docker/open-webui:/app/backend/data
```

**Contents**:
- `webui.db` - SQLite database (users, chats, settings)
- `uploads/` - User uploaded files
- `cache/` - Application cache
- `vector_db/` - Vector embeddings for RAG

**Backup Strategy**:
- Automatic backup before each deployment to `/var/backups/open-webui/`
- Manual backup: `cp /var/lib/docker/open-webui/webui.db ~/backup-$(date +%Y%m%d).db`

## Network

```yaml
networks:
  - ollama-network
```

**Must connect to**:
- `litellm:4000` - For API proxy
- Other services in ollama-network

## Dependencies

```yaml
depends_on:
  - litellm
```

Ensures LiteLLM starts before Open WebUI.

## Nginx Reverse Proxy

**Config Location**: `cryptolabs-ai-platform/services/nginx-configs/webui.ai.cryptolabs.co.za.conf`

**Key Configuration**:
```nginx
upstream open_webui_upstream {
  server 127.0.0.1:8080;  # Host port, not container IP
}

# SSO via WordPress auth_request
location = /__wp_auth_check {
  internal;
  proxy_pass https://cryptolabs.co.za/wp-json/cryptolabs/v1/webui/auth;
  proxy_set_header Cookie $http_cookie;
  # Captures headers from WordPress response
}

location / {
  auth_request /__wp_auth_check;
  
  # Forward SSO headers to Open WebUI
  proxy_set_header X-Webui-Email $auth_email;
  proxy_set_header X-Webui-Name $auth_name;
  proxy_set_header X-User-Api-Key $auth_api_key;
  
  proxy_pass http://open_webui_upstream;
}
```

## GitHub Secrets (Required)

These must be configured in the open-webui GitHub repository:

1. **DOCKER_USERNAME**
   - Docker Hub username
   - Value: `jjziets`

2. **DOCKER_PASSWORD**
   - Docker Hub access token or password
   - Generate at: https://hub.docker.com/settings/security

3. **SSH_PRIVATE_KEY**
   - SSH key for GPU server access
   - File: `~/.ssh/ubuntu_key` (on your Mac)
   - Copy command: `cat ~/.ssh/ubuntu_key | pbcopy`
   - Must have access to: `root@41.193.204.66:101`

## Disaster Recovery

### Complete Rebuild from Scratch

If the GPU server is lost, here's how to recreate:

#### 1. Setup Server
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get update && apt-get install docker-compose-plugin

# Install nginx
apt-get install nginx certbot python3-certbot-nginx
```

#### 2. Clone Repositories
```bash
# Create directories
mkdir -p /home/vast
cd /home/vast

# Clone repositories
git clone https://github.com/jjziets/cryptolabs-ai-platform.git
git clone https://github.com/jjziets/open-webui.git

# Set ownership
chown -R vast:vast cryptolabs-ai-platform open-webui
```

#### 3. Configure Environment
```bash
cd /home/vast/cryptolabs-ai-platform/services

# Create services.env with all required variables
# See cryptolabs-ai-platform/services/services.env.example
# Key variables:
# - LITELLM_MASTER_KEY
# - VLLM_API_KEY  
# - DATABASE_URL
# - LITELLM_MODEL_NAME
```

#### 4. Deploy Nginx Configs
```bash
chmod +x deploy-nginx-configs.sh
sudo ./deploy-nginx-configs.sh
```

#### 5. Get SSL Certificates
```bash
certbot --nginx -d webui.ai.cryptolabs.co.za -d api.ai.cryptolabs.co.za -d wpbm.ai.cryptolabs.co.za
```

#### 6. Start Services
```bash
# Pull images from Docker Hub
docker pull jjziets/open-webui:latest
docker pull jjziets/api-proxy:latest
docker pull jjziets/wordpress-backup-monitor:latest

# Start everything
docker-compose up -d

# Verify
docker ps
curl https://webui.ai.cryptolabs.co.za/
```

## Configuration Files to Backup

For complete disaster recovery, backup these from GPU server:

### Critical Files
- `/home/vast/cryptolabs-ai-platform/services/services.env` - All secrets
- `/var/lib/docker/open-webui/webui.db` - Chat history
- `/etc/nginx/sites-available/*.conf` - Nginx configs (also in git)
- `/etc/letsencrypt/` - SSL certificates

### Backup Command
```bash
# On GPU server
tar -czf ~/cryptolabs-backup-$(date +%Y%m%d).tar.gz \
  /home/vast/cryptolabs-ai-platform/services/services.env \
  /var/lib/docker/open-webui/webui.db \
  /etc/letsencrypt/

# Download to your Mac
scp -P 101 -i ~/.ssh/ubuntu_key \
  root@41.193.204.66:~/cryptolabs-backup-*.tar.gz \
  ~/Backups/
```

## Testing the Deployment

### After Each Deploy:

```bash
# 1. Check image is latest
docker inspect open-webui --format '{{.Image}}'
docker images | grep open-webui

# 2. Check container is running
docker ps | grep open-webui

# 3. Check logs for errors
docker logs open-webui --tail 50 | grep -i error

# 4. Test local access
curl http://localhost:8080/

# 5. Test nginx proxy
curl -I https://webui.ai.cryptolabs.co.za/

# 6. Test SSO
# (Login to WordPress first)
curl -H "Cookie: wordpress_logged_in_xxx=..." https://webui.ai.cryptolabs.co.za/
```

## Monitoring

**GitHub Actions**:
- open-webui builds: https://github.com/jjziets/open-webui/actions
- Container logs: `docker logs open-webui -f`
- nginx logs: `tail -f /var/log/nginx/access.log | grep webui`

## Version Tracking

**Build Arg**: `BUILD_COMMIT` contains git commit hash

**Check deployed version**:
```bash
docker inspect open-webui --format '{{.Config.Labels.commit}}'
```

Or check logs for startup message with commit.

