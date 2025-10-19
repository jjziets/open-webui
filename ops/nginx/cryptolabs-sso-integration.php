<?php
/**
 * Plugin Name: Cryptolabs SSO Integration
 * Description: Handles SSO integration between WordPress and Open WebUI
 * Version: 1.0
 * Author: Cryptolabs
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
        
        // Build WebUI URL with trusted headers via proxy
        $webui_base = 'https://webui.ai.cryptolabs.co.za/';
        
        // Create a form for POST redirect with user data
        ?>
        <!DOCTYPE html>
        <html>
        <head>
            <title>Redirecting to AI Chat...</title>
            <meta charset="utf-8">
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: #f5f5f5;
                }
                .loading {
                    text-align: center;
                }
                .spinner {
                    border: 3px solid #f3f3f3;
                    border-top: 3px solid #3498db;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin: 0 auto 20px;
                }
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
            </style>
        </head>
        <body>
            <div class="loading">
                <div class="spinner"></div>
                <p>Redirecting to AI Chat...</p>
            </div>
            <form id="sso-form" action="<?php echo esc_url($webui_base); ?>" method="GET" style="display:none;">
            </form>
            <script>
                // Store user data in session storage for the WebUI to retrieve
                sessionStorage.setItem('cryptolabs_sso_data', JSON.stringify({
                    email: <?php echo json_encode($user_email); ?>,
                    name: <?php echo json_encode($user_name); ?>,
                    roles: <?php echo json_encode($user_roles); ?>,
                    timestamp: Date.now()
                }));
                
                // Auto-submit form
                document.getElementById('sso-form').submit();
            </script>
        </body>
        </html>
        <?php
        exit;
    }
}

// Add AJAX endpoint for WebUI to validate WordPress session
add_action('wp_ajax_cryptolabs_validate_session', 'cryptolabs_validate_session');
add_action('wp_ajax_nopriv_cryptolabs_validate_session', 'cryptolabs_validate_session');

function cryptolabs_validate_session() {
    // Enable CORS for WebUI domain
    header('Access-Control-Allow-Origin: https://webui.ai.cryptolabs.co.za');
    header('Access-Control-Allow-Credentials: true');
    header('Access-Control-Allow-Methods: POST, GET, OPTIONS');
    header('Access-Control-Allow-Headers: Content-Type');
    
    if (!is_user_logged_in()) {
        wp_send_json_error('Not authenticated', 401);
    }
    
    $current_user = wp_get_current_user();
    
    wp_send_json_success(array(
        'email' => $current_user->user_email,
        'name' => $current_user->display_name,
        'roles' => $current_user->roles,
        'api_key' => get_user_meta($current_user->ID, 'openai_api_key', true) ?: 'sk-CPqwSu2GJcYjE0qrexd5rw'
    ));
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
    if ($args->theme_location == 'primary' && is_user_logged_in()) {
        $items .= '<li class="menu-item"><a href="/ai-chat/">AI Chat</a></li>';
    }
    return $items;
}

// Add admin menu for configuration
add_action('admin_menu', 'cryptolabs_sso_admin_menu');

function cryptolabs_sso_admin_menu() {
    add_options_page(
        'Cryptolabs SSO Settings',
        'Cryptolabs SSO',
        'manage_options',
        'cryptolabs-sso',
        'cryptolabs_sso_settings_page'
    );
}

function cryptolabs_sso_settings_page() {
    if (isset($_POST['submit'])) {
        update_option('cryptolabs_webui_url', sanitize_text_field($_POST['webui_url']));
        update_option('cryptolabs_api_url', sanitize_text_field($_POST['api_url']));
        update_option('cryptolabs_api_key', sanitize_text_field($_POST['api_key']));
        echo '<div class="notice notice-success"><p>Settings saved!</p></div>';
    }
    
    $webui_url = get_option('cryptolabs_webui_url', 'https://webui.ai.cryptolabs.co.za');
    $api_url = get_option('cryptolabs_api_url', 'https://api.ai.cryptolabs.co.za/v1');
    $api_key = get_option('cryptolabs_api_key', 'sk-CPqwSu2GJcYjE0qrexd5rw');
    ?>
    <div class="wrap">
        <h1>Cryptolabs SSO Settings</h1>
        <form method="post" action="">
            <table class="form-table">
                <tr>
                    <th scope="row"><label for="webui_url">WebUI URL</label></th>
                    <td><input type="url" id="webui_url" name="webui_url" value="<?php echo esc_attr($webui_url); ?>" class="regular-text" /></td>
                </tr>
                <tr>
                    <th scope="row"><label for="api_url">API URL</label></th>
                    <td><input type="url" id="api_url" name="api_url" value="<?php echo esc_attr($api_url); ?>" class="regular-text" /></td>
                </tr>
                <tr>
                    <th scope="row"><label for="api_key">API Key</label></th>
                    <td><input type="text" id="api_key" name="api_key" value="<?php echo esc_attr($api_key); ?>" class="regular-text" /></td>
                </tr>
            </table>
            <?php submit_button(); ?>
        </form>
        
        <h2>Test Connection</h2>
        <button type="button" class="button" onclick="testConnection()">Test API Connection</button>
        <div id="test-result"></div>
        
        <script>
        function testConnection() {
            jQuery('#test-result').html('<p>Testing...</p>');
            jQuery.ajax({
                url: '<?php echo esc_js($api_url); ?>/models',
                headers: {
                    'Authorization': 'Bearer <?php echo esc_js($api_key); ?>'
                },
                success: function(data) {
                    jQuery('#test-result').html('<p style="color:green;">✓ Connection successful! Found ' + data.data.length + ' models.</p>');
                },
                error: function(xhr) {
                    jQuery('#test-result').html('<p style="color:red;">✗ Connection failed: ' + xhr.statusText + '</p>');
                }
            });
        }
        </script>
    </div>
    <?php
}

// Register activation hook
register_activation_hook(__FILE__, 'cryptolabs_sso_activate');

function cryptolabs_sso_activate() {
    // Create AI Chat page if it doesn't exist
    if (!get_page_by_path('ai-chat')) {
        wp_insert_post(array(
            'post_title' => 'AI Chat',
            'post_name' => 'ai-chat',
            'post_status' => 'publish',
            'post_type' => 'page',
            'post_content' => '<!-- Redirects to WebUI -->'
        ));
    }
}
