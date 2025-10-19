# WordPress Plugin Configuration for SSO Integration

## Overview
This guide explains how to configure the Cryptolabs AI Gateway plugin (v1.2.5) to work with the Open WebUI SSO integration.

## WordPress Side Configuration

### Step 1: Create SSO Integration File

Create a new file in your WordPress installation: `wp-content/mu-plugins/cryptolabs-sso-integration.php`

```php
<?php
/**
 * Plugin Name: Cryptolabs SSO Integration
 * Description: Handles SSO integration between WordPress and Open WebUI
 * Version: 1.0
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Hook into the AI chat redirect
add_action('template_redirect', 'cryptolabs_sso_redirect');

function cryptolabs_sso_redirect() {
    // Check if this is the AI chat page
    if (is_page('ai-chat') || $_SERVER['REQUEST_URI'] === '/ai-chat/' || $_SERVER['REQUEST_URI'] === '/ai-chat') {
        
        // Check if user is logged in
        if (!is_user_logged_in()) {
            // Redirect to WordPress login with return URL
            $login_url = wp_login_url('https://webui.ai.cryptolabs.co.za/');
            wp_redirect($login_url);
            exit;
        }
        
        // Get current user data
        $current_user = wp_get_current_user();
        $user_email = $current_user->user_email;
        $user_name = $current_user->display_name;
        $user_roles = implode(',', $current_user->roles);
        
        // Generate a secure token for this session
        $token = wp_create_nonce('cryptolabs_sso_' . $user_email);
        
        // Store user data in transient for proxy to retrieve
        set_transient('cryptolabs_sso_' . $token, array(
            'email' => $user_email,
            'name' => $user_name,
            'roles' => $user_roles,
            'api_key' => get_user_meta($current_user->ID, 'openai_api_key', true) ?: 'sk-CPqwSu2GJcYjE0qrexd5rw'
        ), 300); // 5 minutes expiry
        
        // Build WebUI URL with SSO token
        $webui_url = 'https://webui.ai.cryptolabs.co.za/sso-auth?token=' . $token;
        
        // Redirect to WebUI
        wp_redirect($webui_url);
        exit;
    }
}

// API endpoint for WebUI to validate SSO tokens
add_action('rest_api_init', function () {
    register_rest_route('cryptolabs/v1', '/validate-sso', array(
        'methods' => 'POST',
        'callback' => 'cryptolabs_validate_sso_token',
        'permission_callback' => '__return_true'
    ));
});

function cryptolabs_validate_sso_token($request) {
    $token = $request->get_param('token');
    
    if (!$token) {
        return new WP_Error('missing_token', 'Token is required', array('status' => 400));
    }
    
    // Retrieve user data from transient
    $user_data = get_transient('cryptolabs_sso_' . $token);
    
    if (!$user_data) {
        return new WP_Error('invalid_token', 'Invalid or expired token', array('status' => 401));
    }
    
    // Delete transient after use (one-time token)
    delete_transient('cryptolabs_sso_' . $token);
    
    return rest_ensure_response($user_data);
}

// Add custom headers to AI Gateway proxy requests
add_filter('cryptolabs_ai_gateway_headers', 'add_sso_headers', 10, 2);

function add_sso_headers($headers, $user_id) {
    if ($user_id) {
        $user = get_user_by('id', $user_id);
        if ($user) {
            $headers['X-Webui-Email'] = $user->user_email;
            $headers['X-Webui-Name'] = $user->display_name;
            $headers['X-Webui-Groups'] = implode(',', $user->roles);
            $headers['X-User-Api-Key'] = get_user_meta($user_id, 'openai_api_key', true) ?: 'sk-CPqwSu2GJcYjE0qrexd5rw';
        }
    }
    return $headers;
}

// Add menu item for AI Chat
add_filter('wp_nav_menu_items', 'add_ai_chat_menu_item', 10, 2);

function add_ai_chat_menu_item($items, $args) {
    if ($args->theme_location == 'primary') {
        $items .= '<li class="menu-item"><a href="/ai-chat/">AI Chat</a></li>';
    }
    return $items;
}
```

### Step 2: Configure Cryptolabs AI Gateway Plugin

1. **Access WordPress Admin**
   ```
   https://www.cryptolabs.co.za/wp-admin/
   ```

2. **Navigate to Plugin Settings**
   - Go to: Settings → Cryptolabs AI Gateway

3. **Configure API Settings**
   ```
   API Endpoint: https://api.ai.cryptolabs.co.za/v1
   API Key: sk-CPqwSu2GJcYjE0qrexd5rw
   Model: qwen3-coder-30b
   Max Tokens: 4096
   Temperature: 0.7
   ```

4. **Configure SSO Settings** (if available in plugin)
   ```
   Enable SSO: Yes
   SSO Type: Trusted Headers
   WebUI URL: https://webui.ai.cryptolabs.co.za
   Redirect After Logout: https://www.cryptolabs.co.za/
   ```

### Step 3: Create Custom Nginx Configuration for WordPress

Create `/etc/nginx/snippets/wordpress-sso-proxy.conf`:

```nginx
# SSO Proxy configuration for WordPress
location /webui-proxy/ {
    # Check if user is authenticated (requires custom auth check)
    access_by_lua_block {
        -- This requires OpenResty/Nginx with Lua module
        -- Alternative: Use auth_request module
    }
    
    # Strip /webui-proxy/ from the URI
    rewrite ^/webui-proxy/(.*) /$1 break;
    
    # Proxy to WebUI
    proxy_pass https://webui.ai.cryptolabs.co.za;
    
    # Add authentication headers
    proxy_set_header X-Webui-Email $http_x_wp_user_email;
    proxy_set_header X-Webui-Name $http_x_wp_user_name;
    proxy_set_header X-Webui-Groups $http_x_wp_user_roles;
    proxy_set_header X-User-Api-Key "sk-CPqwSu2GJcYjE0qrexd5rw";
    
    # Standard proxy headers
    proxy_set_header Host webui.ai.cryptolabs.co.za;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    
    # Timeouts
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

### Step 4: Test Plugin Configuration

1. **Test API Connection**
   - In WordPress admin, go to Cryptolabs AI Gateway settings
   - Click "Test Connection"
   - Should return: "Connection successful"

2. **Test SSO Flow**
   - Log in to WordPress
   - Navigate to: https://www.cryptolabs.co.za/ai-chat/
   - Should redirect to WebUI without requiring login

3. **Test API Calls**
   ```bash
   curl -X POST https://www.cryptolabs.co.za/wp-json/cryptolabs/v1/chat \
     -H "Content-Type: application/json" \
     -H "X-WP-Nonce: YOUR_NONCE" \
     -d '{
       "message": "Hello, AI!",
       "model": "qwen3-coder-30b"
     }'
   ```

## Troubleshooting

### Common Issues

1. **SSO Not Working**
   - Check if mu-plugin is loaded: `wp plugin list --status=must-use`
   - Verify transients are working: `wp transient list`
   - Check WebUI logs for header values

2. **API Connection Failed**
   - Verify API endpoint is accessible
   - Check API key is correct
   - Test direct API call to LiteLLM

3. **Redirect Loop**
   - Clear WordPress cookies
   - Check redirect rules in .htaccess
   - Verify WebUI redirect URL

### Debug Mode

Add to `wp-config.php`:
```php
define('WP_DEBUG', true);
define('WP_DEBUG_LOG', true);
define('WP_DEBUG_DISPLAY', false);
define('CRYPTOLABS_SSO_DEBUG', true);
```

Check logs at: `/wp-content/debug.log`

## Security Considerations

1. **API Key Security**
   - Store API key in wp-config.php instead of database:
     ```php
     define('CRYPTOLABS_API_KEY', 'sk-CPqwSu2GJcYjE0qrexd5rw');
     ```

2. **Token Security**
   - Tokens are one-time use only
   - 5-minute expiry
   - WordPress nonce validation

3. **Header Validation**
   - WebUI should validate header format
   - Check email domain restrictions
   - Validate role permissions

## Advanced Configuration

### Custom User Roles Mapping
```php
add_filter('cryptolabs_sso_user_groups', function($groups, $user) {
    $role_mapping = array(
        'administrator' => 'admin',
        'editor' => 'power_user',
        'author' => 'user',
        'subscriber' => 'viewer'
    );
    
    $mapped_groups = array();
    foreach ($user->roles as $role) {
        if (isset($role_mapping[$role])) {
            $mapped_groups[] = $role_mapping[$role];
        }
    }
    
    return implode(',', $mapped_groups);
}, 10, 2);
```

### Custom API Key Per User
```php
add_filter('cryptolabs_user_api_key', function($api_key, $user_id) {
    $user_key = get_user_meta($user_id, 'personal_api_key', true);
    return $user_key ?: $api_key;
}, 10, 2);
```
