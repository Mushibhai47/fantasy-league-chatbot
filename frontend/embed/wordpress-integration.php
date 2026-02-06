<?php
/**
 * Razzball Fantasy Baseball Chatbot - WordPress Integration
 *
 * This file provides two methods to embed the chatbot on WordPress:
 * 1. Simple shortcode for quick integration
 * 2. Full plugin with user integration
 *
 * Installation Instructions:
 * - Add this code to your theme's functions.php file
 * - OR create a WordPress plugin with this code
 * - Use shortcode [razzball_chatbot] on any page
 */

// Method 1: Simple Shortcode (Easiest)
function razzball_chatbot_simple_shortcode() {
    $embed_url = 'https://chatbot.razzball.com/embed';

    return sprintf(
        '<iframe
            src="%s"
            width="100%%"
            height="600px"
            frameborder="0"
            style="border: 1px solid #e1e8ed; border-radius: 8px;"
            id="razzball-chatbot-embed"
            title="Razzball Fantasy Baseball Assistant"
        ></iframe>',
        esc_url($embed_url)
    );
}
add_shortcode('razzball_chatbot', 'razzball_chatbot_simple_shortcode');

// Method 2: Advanced Integration with User Email Pass-through
function razzball_chatbot_advanced_shortcode($atts) {
    $atts = shortcode_atts(array(
        'height' => '600px',
        'width' => '100%'
    ), $atts);

    $embed_url = 'https://chatbot.razzball.com/embed';
    $user = wp_get_current_user();
    $user_email = $user->user_email;

    // Generate unique ID for this iframe
    $iframe_id = 'razzball-chatbot-' . uniqid();

    ob_start();
    ?>
    <div class="razzball-chatbot-container">
        <iframe
            src="<?php echo esc_url($embed_url); ?>"
            width="<?php echo esc_attr($atts['width']); ?>"
            height="<?php echo esc_attr($atts['height']); ?>"
            frameborder="0"
            style="border: 1px solid #e1e8ed; border-radius: 8px;"
            id="<?php echo esc_attr($iframe_id); ?>"
            title="Razzball Fantasy Baseball Assistant"
        ></iframe>
    </div>

    <script>
    (function() {
        var iframe = document.getElementById('<?php echo esc_js($iframe_id); ?>');

        // Wait for iframe to load
        iframe.addEventListener('load', function() {
            // Send user info to chatbot iframe
            iframe.contentWindow.postMessage({
                type: 'USER_INFO',
                email: '<?php echo esc_js($user_email); ?>',
                username: '<?php echo esc_js($user->user_login); ?>',
                displayName: '<?php echo esc_js($user->display_name); ?>'
            }, 'https://chatbot.razzball.com');
        });

        // Listen for messages from iframe (optional - for analytics)
        window.addEventListener('message', function(event) {
            if (event.origin !== 'https://chatbot.razzball.com') return;

            // Handle chatbot events (e.g., track usage)
            if (event.data.type === 'CHAT_SENT') {
                console.log('User sent a message to chatbot');
                // Can send to analytics here
            }
        });
    })();
    </script>
    <?php

    return ob_get_clean();
}
add_shortcode('razzball_chatbot_advanced', 'razzball_chatbot_advanced_shortcode');

// Method 3: Check Paid Memberships Pro Integration
function razzball_chatbot_with_pmp_check($atts) {
    // Check if user has active membership
    if (function_exists('pmpro_hasMembershipLevel')) {
        // Adjust membership level IDs as needed
        $allowed_levels = array(1, 2, 3); // Update with your actual level IDs

        if (!pmpro_hasMembershipLevel($allowed_levels)) {
            return '<div class="razzball-chatbot-locked">
                <p>🔒 This Fantasy Baseball Assistant is available to premium members only.</p>
                <p><a href="' . pmpro_url('levels') . '" class="btn btn-primary">Upgrade Now</a></p>
            </div>';
        }
    }

    // User has access - show chatbot
    return razzball_chatbot_advanced_shortcode($atts);
}
add_shortcode('razzball_chatbot_premium', 'razzball_chatbot_with_pmp_check');

// Add custom CSS for the chatbot container
function razzball_chatbot_styles() {
    ?>
    <style>
        .razzball-chatbot-container {
            max-width: 1200px;
            margin: 20px auto;
        }

        .razzball-chatbot-locked {
            max-width: 600px;
            margin: 40px auto;
            padding: 40px;
            text-align: center;
            background: #f5f7fa;
            border: 2px solid #e1e8ed;
            border-radius: 12px;
        }

        .razzball-chatbot-locked p {
            font-size: 16px;
            margin-bottom: 20px;
        }

        .razzball-chatbot-locked .btn {
            display: inline-block;
            padding: 12px 32px;
            background: #FF6B35;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            transition: background 0.2s;
        }

        .razzball-chatbot-locked .btn:hover {
            background: #E55A25;
        }
    </style>
    <?php
}
add_action('wp_head', 'razzball_chatbot_styles');

/**
 * Usage Instructions:
 *
 * 1. Simple Embed (no user integration):
 *    [razzball_chatbot]
 *
 * 2. Advanced Embed (with user email):
 *    [razzball_chatbot_advanced]
 *
 * 3. Premium Only (requires Paid Memberships Pro):
 *    [razzball_chatbot_premium]
 *
 * 4. Custom height/width:
 *    [razzball_chatbot_advanced height="800px" width="100%"]
 *
 * Example Page Content:
 *
 * <h1>Your Fantasy Baseball Assistant</h1>
 * <p>Get expert advice on your fantasy baseball team!</p>
 * [razzball_chatbot_premium]
 *
 */
?>
