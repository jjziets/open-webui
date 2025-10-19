# Open WebUI + WordPress SSO Integration with Nginx

This directory contains all the configuration files and scripts needed to set up SSO integration between WordPress and Open WebUI using Nginx as the reverse proxy.

## Quick Start

1. **SSH to the server:**
   ```bash
   ssh -i ~/.ssh/ubuntu_key -p 101 root@41.193.204.66
   ```

2. **Run the deployment script:**
   ```bash
   bash deploy-sso-nginx.sh
   ```

3. **Configure WordPress:**
   - Upload `cryptolabs-sso-integration.php` to `wp-content/plugins/`
   - Activate the plugin in WordPress admin
   - Configure API settings in Settings → Cryptolabs SSO

## Files in this Directory

### Configuration Files
- `webui.ai.cryptolabs.co.za.conf` - Nginx config for Open WebUI
- `api.ai.cryptolabs.co.za.conf` - Nginx config for LiteLLM API  
- `wpbm.ai.cryptolabs.co.za.conf` - Nginx config for WordPress Backup Monitor
- `cryptolabs.co.za-redirects.conf` - Redirect rules for WordPress

### Documentation
- `SSO_SETUP_GUIDE.md` - Comprehensive SSO setup guide
- `WORDPRESS_PLUGIN_CONFIG.md` - WordPress plugin configuration guide

### Scripts
- `deploy-sso-nginx.sh` - Automated deployment script
- `cryptolabs-sso-integration.php` - WordPress plugin for SSO

## Key Information

### Domains
- WebUI: https://webui.ai.cryptolabs.co.za
- API: https://api.ai.cryptolabs.co.za
- WPBM: https://wpbm.ai.cryptolabs.co.za

### Credentials
- API Key: `sk-CPqwSu2GJcYjE0qrexd5rw`
- Server: `41.193.204.66:101`
- WordPress sFTP: `crypthbfgw@cryptolabs.co.za`

### Testing

Test the API endpoint:
```bash
curl https://api.ai.cryptolabs.co.za/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-CPqwSu2GJcYjE0qrexd5rw" \
  -d '{
    "model": "qwen3-coder-30b",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

## Troubleshooting

### Check Services
```bash
# Container status
docker ps --format 'table {{.Names}}\t{{.Ports}}'

# Nginx status
systemctl status nginx

# Check logs
docker logs --tail=100 open-webui
tail -f /var/log/nginx/error.log
```

### Update Container IPs
If containers restart and get new IPs:
```bash
/usr/local/bin/update-nginx-upstreams.sh
```

### SSL Certificate Renewal
```bash
certbot renew --dry-run  # Test
certbot renew           # Actual renewal
```

## Architecture Overview

```
WordPress (cryptolabs.co.za)
    ↓
    User clicks /ai-chat/
    ↓
    WordPress Plugin checks auth
    ↓
    Redirect to WebUI with SSO data
    ↓
Open WebUI (webui.ai.cryptolabs.co.za)
    ↓
    Validates SSO headers
    ↓
    User accesses AI chat
    ↓
    API calls to LiteLLM
    ↓
LiteLLM API (api.ai.cryptolabs.co.za)
```

## Support

For issues or questions:
1. Check the logs first
2. Verify all containers are running
3. Test each service individually
4. Check SSL certificates are valid