#!/bin/bash
# Deploy script for Open WebUI + WordPress SSO with Nginx
# Run on the GPU server: ssh -i ~/.ssh/ubuntu_key -p 101 root@41.193.204.66

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_KEY="sk-CPqwSu2GJcYjE0qrexd5rw"
DOMAINS="webui.ai.cryptolabs.co.za api.ai.cryptolabs.co.za wpbm.ai.cryptolabs.co.za"

echo -e "${GREEN}=== Open WebUI + WordPress SSO Deployment Script ===${NC}"
echo -e "${YELLOW}This script will configure Nginx for SSO integration${NC}"

# Function to print status
print_status() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   print_error "This script must be run as root"
   exit 1
fi

# Step 1: Check Docker containers
print_status "Checking Docker containers..."
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Ports}}'

# Get container IPs
WEBUI_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' open-webui 2>/dev/null || echo "")
LITELLM_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' litellm 2>/dev/null || echo "")
API_PROXY_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' api-proxy 2>/dev/null || echo "")

if [[ -z "$WEBUI_IP" ]]; then
    print_error "open-webui container not found or not running"
    exit 1
fi

if [[ -z "$LITELLM_IP" ]]; then
    print_error "litellm container not found or not running"
    exit 1
fi

print_status "Container IPs:"
echo "  WebUI: $WEBUI_IP"
echo "  LiteLLM: $LITELLM_IP"
[[ -n "$API_PROXY_IP" ]] && echo "  API Proxy: $API_PROXY_IP"

# Step 2: Stop and remove Caddy if exists
print_status "Removing Caddy container if exists..."
docker stop caddy 2>/dev/null || true
docker rm caddy 2>/dev/null || true

# Step 3: Install Nginx and Certbot
print_status "Installing Nginx and Certbot..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx certbot python3-certbot-nginx curl jq

# Enable and start Nginx
systemctl enable nginx
systemctl start nginx

# Step 4: Create directories
print_status "Creating Nginx directories..."
mkdir -p /etc/nginx/sites-available /etc/nginx/sites-enabled /etc/nginx/snippets /var/www/letsencrypt

# Step 5: Create Nginx configurations
print_status "Creating Nginx configurations..."

# WebUI configuration
cat > /etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf << EOF
map \$http_upgrade \$connection_upgrade {
  default upgrade;
  ''      close;
}

upstream open_webui_upstream {
  server ${WEBUI_IP}:8080;
  keepalive 32;
}

server {
  listen 80;
  listen [::]:80;
  server_name webui.ai.cryptolabs.co.za;
  
  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
  
  location / {
    return 301 https://\$host\$request_uri;
  }
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name webui.ai.cryptolabs.co.za;

  # SSL will be configured by certbot
  # ssl_certificate     /etc/letsencrypt/live/webui.ai.cryptolabs.co.za/fullchain.pem;
  # ssl_certificate_key /etc/letsencrypt/live/webui.ai.cryptolabs.co.za/privkey.pem;

  client_max_body_size 100m;

  # Comment out for trusted header SSO
  # location = /auth {
  #   return 302 /oauth/oidc/login;
  # }

  # WebSocket support
  location /ws/socket.io {
    proxy_pass http://open_webui_upstream;
    proxy_http_version 1.1;
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection \$connection_upgrade;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
  }

  location / {
    proxy_pass http://open_webui_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Forwarded-Port \$server_port;
    
    # Pass through trusted headers from WordPress
    proxy_set_header X-Webui-Email \$http_x_webui_email;
    proxy_set_header X-Webui-Name \$http_x_webui_name;
    proxy_set_header X-Webui-Groups \$http_x_webui_groups;
    proxy_set_header X-User-Api-Key \$http_x_user_api_key;
    
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
  }

  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
}
EOF

# API configuration
cat > /etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf << EOF
upstream litellm_upstream {
  server ${LITELLM_IP}:4000;
  keepalive 16;
}

server {
  listen 80;
  listen [::]:80;
  server_name api.ai.cryptolabs.co.za;
  
  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
  
  location / {
    return 301 https://\$host\$request_uri;
  }
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name api.ai.cryptolabs.co.za;

  # SSL will be configured by certbot
  # ssl_certificate     /etc/letsencrypt/live/api.ai.cryptolabs.co.za/fullchain.pem;
  # ssl_certificate_key /etc/letsencrypt/live/api.ai.cryptolabs.co.za/privkey.pem;

  client_max_body_size 100m;
  
  proxy_read_timeout 3600s;
  proxy_send_timeout 3600s;
  proxy_connect_timeout 60s;

  location / {
    proxy_pass http://litellm_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_set_header Authorization \$http_authorization;
    proxy_buffering off;
    proxy_cache off;
  }

  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
}
EOF

# WPBM configuration
cat > /etc/nginx/sites-available/wpbm.ai.cryptolabs.co.za.conf << EOF
upstream wpbm_upstream {
  server 127.0.0.1:7777;
  keepalive 16;
}

server {
  listen 80;
  listen [::]:80;
  server_name wpbm.ai.cryptolabs.co.za;
  
  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
  
  location / {
    return 301 https://\$host\$request_uri;
  }
}

server {
  listen 443 ssl http2;
  listen [::]:443 ssl http2;
  server_name wpbm.ai.cryptolabs.co.za;

  # SSL will be configured by certbot
  # ssl_certificate     /etc/letsencrypt/live/wpbm.ai.cryptolabs.co.za/fullchain.pem;
  # ssl_certificate_key /etc/letsencrypt/live/wpbm.ai.cryptolabs.co.za/privkey.pem;

  client_max_body_size 100m;

  location / {
    proxy_pass http://wpbm_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
  }

  location /.well-known/acme-challenge/ {
    root /var/www/letsencrypt;
  }
}
EOF

# Create redirect snippet
cat > /etc/nginx/snippets/cryptolabs.co.za-redirects.conf << 'EOF'
location = /ai-chat {
  return 301 https://webui.ai.cryptolabs.co.za/auth?redirect=%2F;
}

location = /ai-chat/ {
  return 301 https://webui.ai.cryptolabs.co.za/auth?redirect=%2F;
}
EOF

# Step 6: Enable sites
print_status "Enabling Nginx sites..."
ln -sf /etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf /etc/nginx/sites-enabled/
ln -sf /etc/nginx/sites-available/wpbm.ai.cryptolabs.co.za.conf /etc/nginx/sites-enabled/

# Remove default site if exists
rm -f /etc/nginx/sites-enabled/default

# Test configuration
print_status "Testing Nginx configuration..."
nginx -t

# Reload Nginx
print_status "Reloading Nginx..."
systemctl reload nginx

# Step 7: Configure SSL certificates
print_status "Configuring SSL certificates..."
certbot --nginx --non-interactive --agree-tos --email admin@cryptolabs.co.za \
  -d webui.ai.cryptolabs.co.za \
  -d api.ai.cryptolabs.co.za \
  -d wpbm.ai.cryptolabs.co.za || {
    print_warning "Certbot failed. Trying with webroot method..."
    certbot certonly --webroot -w /var/www/letsencrypt \
      --non-interactive --agree-tos --email admin@cryptolabs.co.za \
      -d webui.ai.cryptolabs.co.za \
      -d api.ai.cryptolabs.co.za \
      -d wpbm.ai.cryptolabs.co.za
}

# Step 8: Update Open WebUI for trusted header SSO
print_status "Configuring Open WebUI for SSO..."

# Check if we need to recreate the container with new env vars
if ! docker inspect open-webui | grep -q "WEBUI_AUTH_TRUSTED_EMAIL_HEADER"; then
    print_warning "Recreating Open WebUI container with SSO configuration..."
    
    # Get existing volumes and network
    WEBUI_VOLUME=$(docker inspect open-webui --format '{{range .Mounts}}{{if eq .Type "volume"}}{{.Name}}{{end}}{{end}}' | head -1)
    WEBUI_NETWORK=$(docker inspect open-webui --format '{{range $net, $conf := .NetworkSettings.Networks}}{{$net}}{{end}}' | head -1)
    
    # Stop and remove existing container
    docker stop open-webui
    docker rm open-webui
    
    # Recreate with SSO enabled
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
      -v ${WEBUI_VOLUME:-open-webui}:/app/backend/data \
      --network ${WEBUI_NETWORK:-bridge} \
      ghcr.io/open-webui/open-webui:main
    
    # Wait for container to start
    sleep 10
fi

# Step 9: Test services
print_status "Testing services..."

# Test WebUI
echo -n "Testing WebUI... "
if curl -sSf -o /dev/null -w "%{http_code}" https://webui.ai.cryptolabs.co.za/ | grep -q "200\|302"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Test API
echo -n "Testing API... "
API_RESPONSE=$(curl -s -w "\n%{http_code}" https://api.ai.cryptolabs.co.za/v1/models \
  -H "Authorization: Bearer $API_KEY" | tail -1)
if [[ "$API_RESPONSE" == "200" ]] || [[ "$API_RESPONSE" == "401" ]]; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Test WPBM
echo -n "Testing WPBM... "
if curl -sSf -o /dev/null -w "%{http_code}" https://wpbm.ai.cryptolabs.co.za/ | grep -q "200"; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Test LiteLLM endpoint
print_status "Testing LiteLLM API endpoint..."
curl -s https://api.ai.cryptolabs.co.za/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $API_KEY" \
  -d '{
    "model": "qwen3-coder-30b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 10
  }' | jq .

# Step 10: Create update script
print_status "Creating IP update script..."
cat > /usr/local/bin/update-nginx-upstreams.sh << 'EOF'
#!/bin/bash
# Update Nginx upstream IPs after container restart

WEBUI_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' open-webui 2>/dev/null)
LITELLM_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' litellm 2>/dev/null)

if [[ -n "$WEBUI_IP" ]]; then
    sed -i "s/server [0-9.]*:8080/server $WEBUI_IP:8080/g" /etc/nginx/sites-available/webui.ai.cryptolabs.co.za.conf
fi

if [[ -n "$LITELLM_IP" ]]; then
    sed -i "s/server [0-9.]*:4000/server $LITELLM_IP:4000/g" /etc/nginx/sites-available/api.ai.cryptolabs.co.za.conf
fi

nginx -t && systemctl reload nginx
EOF
chmod +x /usr/local/bin/update-nginx-upstreams.sh

# Create systemd service for auto-update
cat > /etc/systemd/system/nginx-upstream-update.service << EOF
[Unit]
Description=Update Nginx upstream IPs
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/update-nginx-upstreams.sh
EOF

cat > /etc/systemd/system/nginx-upstream-update.timer << EOF
[Unit]
Description=Update Nginx upstream IPs every 5 minutes
Requires=nginx-upstream-update.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable nginx-upstream-update.timer
systemctl start nginx-upstream-update.timer

print_status "Deployment complete!"
echo
echo -e "${GREEN}=== Summary ===${NC}"
echo "WebUI: https://webui.ai.cryptolabs.co.za"
echo "API: https://api.ai.cryptolabs.co.za"
echo "WPBM: https://wpbm.ai.cryptolabs.co.za"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Configure WordPress plugin with API endpoint: https://api.ai.cryptolabs.co.za/v1"
echo "2. Configure WordPress plugin with API key: $API_KEY"
echo "3. Upload the WordPress SSO integration file (see WORDPRESS_PLUGIN_CONFIG.md)"
echo
echo -e "${GREEN}Services are now running!${NC}"
