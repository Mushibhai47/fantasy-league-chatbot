<?php
/**
 * Plugin Name: Razzbot Fantasy Baseball Assistant
 * Plugin URI: https://razzball.com
 * Description: The Fantasy Baseball Assistant by Razzball. Embed Razzbot on any page with [razzbot] or [razzbot_premium].
 * Version: 1.0.0
 * Author: Razzball
 * License: GPL v2 or later
 */

if ( ! defined( 'ABSPATH' ) ) exit;

define( 'RAZZBOT_VERSION',    '1.0.0' );
define( 'RAZZBOT_PLUGIN_DIR', plugin_dir_path( __FILE__ ) );
define( 'RAZZBOT_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

// ─── Rewrite rule: /razzbot/ → standalone embed page ───────────────────────

add_action( 'init', 'razzbot_add_rewrite_rule' );
function razzbot_add_rewrite_rule() {
    add_rewrite_rule( '^razzbot/?$', 'index.php?razzbot_embed=1', 'top' );
}

add_filter( 'query_vars', 'razzbot_query_vars' );
function razzbot_query_vars( $vars ) {
    $vars[] = 'razzbot_embed';
    return $vars;
}

add_action( 'template_redirect', 'razzbot_serve_embed' );
function razzbot_serve_embed() {
    if ( get_query_var( 'razzbot_embed' ) ) {
        include RAZZBOT_PLUGIN_DIR . 'templates/embed-page.php';
        exit;
    }
}

// ─── Shortcodes ─────────────────────────────────────────────────────────────

/**
 * [razzbot] — embeds the chatbot for any logged-in user
 * [razzbot height="750px" width="100%"] — optional size overrides
 */
add_shortcode( 'razzbot', 'razzbot_shortcode' );
function razzbot_shortcode( $atts ) {
    $atts = shortcode_atts( [
        'height' => '750px',
        'width'  => '100%',
    ], $atts );

    $embed_url = home_url( '/razzbot/' );

    return sprintf(
        '<div class="razzbot-container"><iframe src="%s" width="%s" height="%s" frameborder="0" style="border:none;border-radius:8px;display:block;" title="Razzbot Fantasy Baseball Assistant" allowfullscreen></iframe></div>',
        esc_url( $embed_url ),
        esc_attr( $atts['width'] ),
        esc_attr( $atts['height'] )
    );
}

/**
 * [razzbot_premium] — same as [razzbot] but requires Paid Memberships Pro membership
 */
add_shortcode( 'razzbot_premium', 'razzbot_premium_shortcode' );
function razzbot_premium_shortcode( $atts ) {
    if ( function_exists( 'pmpro_hasMembershipLevel' ) && ! pmpro_hasMembershipLevel() ) {
        $levels_url = function_exists( 'pmpro_url' ) ? pmpro_url( 'levels' ) : home_url( '/membership-account/membership-levels/' );
        return '<div class="razzbot-locked">'
             . '<p>&#x1F512; The Fantasy Baseball Assistant is available to premium members only.</p>'
             . '<p><a href="' . esc_url( $levels_url ) . '" class="razzbot-upgrade-btn">Upgrade Now</a></p>'
             . '</div>';
    }
    return razzbot_shortcode( $atts );
}

// ─── Front-end CSS for container / locked state ─────────────────────────────

add_action( 'wp_head', 'razzbot_inline_styles' );
function razzbot_inline_styles() {
    echo '<style>
.razzbot-container { max-width: 1200px; margin: 20px auto; }
.razzbot-locked {
    max-width: 600px; margin: 40px auto; padding: 40px;
    text-align: center; background: #f5f7fa;
    border: 2px solid #e1e8ed; border-radius: 12px;
}
.razzbot-locked p { font-size: 16px; margin-bottom: 20px; }
.razzbot-upgrade-btn {
    display: inline-block; padding: 12px 32px;
    background: #FF6B35; color: #fff;
    text-decoration: none; border-radius: 8px;
    font-weight: 600;
}
.razzbot-upgrade-btn:hover { background: #E55A25; color: #fff; }
</style>';
}

// ─── Activation / Deactivation ───────────────────────────────────────────────

register_activation_hook( __FILE__, 'razzbot_activate' );
function razzbot_activate() {
    razzbot_add_rewrite_rule();
    flush_rewrite_rules();
}

register_deactivation_hook( __FILE__, 'razzbot_deactivate' );
function razzbot_deactivate() {
    flush_rewrite_rules();
}
