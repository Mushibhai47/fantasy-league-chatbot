<?php
/**
 * Plugin Name: Razzbot Fantasy Baseball Assistant
 * Plugin URI: https://razzball.com
 * Description: The Fantasy Baseball Assistant by Razzball. Drop [razzball_chatbot] on any page.
 * Version: 1.0.0
 * Author: Razzball
 * License: GPL v2 or later
 */

if ( ! defined( 'ABSPATH' ) ) exit;

define( 'RAZZBOT_VERSION',    '1.1.0' );
define( 'RAZZBOT_PLUGIN_URL', plugin_dir_url( __FILE__ ) );

// ─── Enqueue CSS & JS only on the page that uses the shortcode ──────────────
// Uses wp_enqueue_scripts + has_shortcode() — the correct WP way to
// guarantee assets are NEVER loaded on other pages or posts.

add_action( 'wp_enqueue_scripts', 'razzbot_conditional_enqueue' );
function razzbot_conditional_enqueue() {
    global $post;
    if ( ! is_a( $post, 'WP_Post' ) || ! has_shortcode( $post->post_content, 'razzball_chatbot' ) ) {
        return;
    }
    wp_enqueue_style(
        'razzbot-css',
        RAZZBOT_PLUGIN_URL . 'assets/embed-v2.css',
        [],
        RAZZBOT_VERSION
    );
    wp_enqueue_script(
        'razzbot-js',
        RAZZBOT_PLUGIN_URL . 'assets/embed-v2.js',
        [],
        RAZZBOT_VERSION,
        true  // load in footer
    );

    // Pass the logged-in WordPress user's email to the JS so the message
    // counter is tied to their WP account, not a random per-device ID
    $user = wp_get_current_user();
    if ( $user->ID ) {
        wp_add_inline_script(
            'razzbot-js',
            'window.razzbotUserId = ' . wp_json_encode( $user->user_email ) . ';',
            'before'
        );
    }
}

// ─── Shortcode: [razzball_chatbot] ──────────────────────────────────────────

add_shortcode( 'razzball_chatbot', 'razzball_chatbot_shortcode' );
function razzball_chatbot_shortcode( $atts ) {
    $atts        = shortcode_atts( [ 'sport' => '' ], $atts, 'razzball_chatbot' );
    $force_sport = sanitize_text_field( $atts['sport'] ); // 'mlb', 'nfl', or ''

    // Sport-specific copy
    $is_nfl       = ( $force_sport === 'nfl' );
    $is_mlb       = ( $force_sport === 'mlb' );
    $sport_label  = $is_nfl ? 'Football' : 'Baseball';
    $upload_icon  = $is_nfl ? '🏈' : ( $is_mlb ? '⚾' : '📄' );
    $upload_hint  = $is_nfl
        ? 'Upload your Fantrax NFL "All Players" CSV export'
        : 'Upload a CSV from Fantrax, CBS, or NFBC — or connect Yahoo / ESPN';
    $placeholder  = $is_nfl
        ? 'Ask me about your NFL fantasy team...'
        : 'Ask me anything about your fantasy baseball team...';

    ob_start();

    // Inject force-sport JS variable so the widget locks to this sport
    if ( $force_sport ) {
        echo '<script>window.razzbotForceSport=' . wp_json_encode( $force_sport ) . ';</script>';
    }
    ?>
    <div id="razzball-chatbot-embed">

        <!-- Setup Screen (first time users) -->
        <div id="setup-screen" class="screen active">
            <div class="setup-container">
                <div class="logo-section">
                    <h1><?php echo $is_nfl ? '🏈' : ''; ?> Razzbot</h1>
                    <p>The Fantasy <?php echo esc_html( $sport_label ); ?> Assistant by Razzball</p>
                </div>

                <div class="setup-step" id="step-api-key" style="display: none;">
                    <h2>OpenAI API Key (Optional)</h2>
                    <p class="step-description">
                        Add your own API key for unlimited messages, or use our free tier (100 messages/month).
                        <a href="https://platform.openai.com/api-keys" target="_blank">Get an API key here</a>
                    </p>
                    <div class="input-group">
                        <input type="password" id="api-key-input" placeholder="sk-...your-api-key" autocomplete="off" />
                        <button id="save-api-key-btn" class="btn btn-primary">Save API Key</button>
                        <button id="skip-api-key-btn" class="btn btn-secondary">Use Free Tier (7/day)</button>
                    </div>
                    <div id="api-key-status" class="status-message"></div>
                </div>

                <div class="setup-step" id="step-upload">
                    <h2>Load Your League</h2>
                    <p class="step-description"><?php echo esc_html( $upload_hint ); ?></p>

                    <div id="yahoo-status" class="status-message"></div>

                    <?php if ( ! $is_nfl ) : ?>
                    <button id="yahoo-connect-btn-upload" class="btn btn-primary" style="width:100%; margin-bottom:8px; background:#6001d2; border-color:#6001d2;" onclick="window.location.href='https://valiant-healing-production-ce05.up.railway.app/api/yahoo/auth'">⚾ Connect Yahoo Fantasy League</button>

                    <div style="margin-bottom:12px; padding:12px; border:1px solid #eee; border-radius:6px; background:#fafafa;">
                        <label style="font-weight:600; display:block; margin-bottom:6px; font-size:13px;">⚾ Connect ESPN Fantasy League</label>
                        <p style="font-size:12px; color:#444; margin:0 0 8px; line-height:1.6;">
                            <strong>Step 1:</strong> Click <strong>Copy Code</strong> below.<br>
                            <strong>Step 2:</strong> In Chrome: press <kbd style="background:#eee;padding:1px 4px;border-radius:3px;">Ctrl+D</kbd> → <em>Edit...</em> → paste the code as the URL → Save.<br>
                            <strong>Step 3:</strong> Go to your <a href="https://fantasy.espn.com/baseball/league" target="_blank">ESPN Fantasy Baseball league</a> page, click the bookmark.
                        </p>
                        <textarea id="espn-bm-code-upload" rows="2" readonly style="width:100%;font-size:10px;padding:6px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;resize:none;background:#f8f8f8;color:#333;font-family:monospace;" placeholder="Loading..."></textarea>
                        <button onclick="var t=document.getElementById('espn-bm-code-upload');t.select();document.execCommand('copy');this.textContent='Copied!';" style="width:100%;margin-top:6px;padding:8px;background:#cc0000;color:#fff;border:none;border-radius:4px;font-weight:700;cursor:pointer;font-size:13px;">Copy Code</button>
                    </div>

                    <p style="text-align:center; font-size:13px; color:#888; margin:8px 0;">or upload a CSV</p>
                    <?php endif; ?>

                    <div class="upload-area" id="upload-area">
                        <div class="upload-icon"><?php echo esc_html( $upload_icon ); ?></div>
                        <p>Drag and drop your league file here</p>
                        <p class="upload-or">or</p>
                        <input type="file" id="file-input" accept=".csv,.xls,.xlsx" style="display: none;" />
                        <button id="browse-btn" class="btn btn-secondary">Browse Files</button>
                    </div>
                    <div id="upload-status" class="status-message"></div>
                    <p style="text-align:center; margin-top: 12px; font-size: 13px; color: #888;">or</p>
                    <button id="skip-upload-btn" class="btn btn-secondary" style="width:100%; margin-top: 4px;">Skip — just ask about players</button>
                </div>

                <div class="setup-step" id="step-ready" style="display: none;">
                    <h2>Setup Your Preferences</h2>
                    <p class="step-description">
                        Your roster is loaded! Choose your team and league format so buttons work automatically.
                    </p>
                    <div class="input-group" style="margin-bottom: 12px;">
                        <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #555;">Your Team</label>
                        <select id="team-selector" style="padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; width: 100%; background: white;">
                            <option value="">-- Select your team --</option>
                        </select>
                    </div>
                    <!-- MLB: league format selector -->
                    <div id="mlb-format-section" class="input-group" style="margin-bottom: 16px;">
                        <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #555;">League Format</label>
                        <select id="league-type-selector" style="padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; width: 100%; background: white;">
                            <option value="MLB12">MLB12 (12-team mixed, 5x5)</option>
                            <option value="MLB12_5x5OBP">MLB12_5x5OBP (12-team mixed, OBP)</option>
                            <option value="MLB12_6x6OBP">MLB12_6x6OBP (12-team mixed, 6x6 OBP)</option>
                            <option value="MLB12_6X6HLD">MLB12_6X6HLD (12-team mixed, 6x6 HLD)</option>
                            <option value="MLB12_6X6QS">MLB12_6X6QS (12-team mixed, 6x6 QS)</option>
                            <option value="MLB15">MLB15 (15-team mixed, 5x5)</option>
                            <option value="MLB15_5x5OBP">MLB15_5x5OBP (15-team mixed, OBP)</option>
                            <option value="MLB10">MLB10 (10-team mixed)</option>
                            <option value="AL12">AL12 (12-team AL-only)</option>
                            <option value="NL12">NL12 (12-team NL-only)</option>
                        </select>
                    </div>
                    <!-- NFL: scoring preset selector (shown only for NFL leagues) -->
                    <div id="nfl-scoring-section" class="input-group" style="display: none; margin-bottom: 16px;">
                        <label style="display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: #555;">Scoring Format</label>
                        <select id="nfl-scoring-preset-selector" style="padding: 10px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; width: 100%; background: white;">
                            <option value="half_ppr">Half-PPR (default)</option>
                            <option value="ppr">Full PPR</option>
                            <option value="standard">Standard (no PPR)</option>
                            <option value="superflex_half_ppr">Superflex Half-PPR</option>
                        </select>
                    </div>
                    <button id="start-chat-btn" class="btn btn-primary btn-large">Start Chatting</button>
                </div>
            </div>
        </div>

        <!-- Chat Screen (main interface) -->
        <div id="chat-screen" class="screen">
            <div class="chat-header">
                <h3>Razzbot</h3>
                <div class="header-actions">
                    <span id="league-indicator" class="league-badge">League Loaded</span>
                    <button id="settings-btn" class="icon-btn" title="Settings">⚙️</button>
                </div>
            </div>

            <div id="chat-messages" class="chat-messages">
                <div class="message bot-message">
                    <div class="message-content">
                        <p>Welcome to Razzbot! Load your team by clicking the Settings button. For <strong>MLB</strong>: use the full league export from NFBC, Fantrax, or CBSSports. For <strong>NFL</strong>: use the Fantrax "All Players" CSV export — we auto-detect it. (We have a link at <a href="https://razzball.com/rotodeluxe" target="_blank">razzball.com/rotodeluxe</a> if you need help.)</p>
                        <p>Choose your Team name and League Format, then use the buttons below for a <strong>League Overview</strong>, <strong>Team Overview</strong>, <strong>Pickups</strong>, and <strong>Start/Sit</strong> recommendations powered by Razzball projections.</p>
                    </div>
                </div>
            </div>

            <div class="chat-input-container">
                <textarea id="chat-input" placeholder="<?php echo esc_attr( $placeholder ); ?>" rows="2"></textarea>
                <button id="send-btn" class="btn btn-primary">
                    <span id="send-icon">Send</span>
                    <span id="loading-icon" style="display: none;">●●●</span>
                </button>
            </div>

            <div id="message-counter" style="display: none; text-align: center; padding: 8px; font-size: 13px; color: #666;"></div>

            <!-- MLB quick-action buttons -->
            <div class="quick-actions" id="mlb-quick-actions">
                <div class="btn-category">
                    <span class="btn-category-label">Pickups:</span>
                    <button class="quick-action-btn" data-query="today pickups">Today</button>
                    <button class="quick-action-btn" data-query="tomorrow pickups">Tomorrow</button>
                    <button class="quick-action-btn" data-query="weekly pickups">Weekly</button>
                </div>
                <div class="btn-category">
                    <span class="btn-category-label">Start/Sit:</span>
                    <button class="quick-action-btn team-action" data-query="today start/sit {team}">Today</button>
                    <button class="quick-action-btn team-action" data-query="tomorrow start/sit {team}">Tomorrow</button>
                    <button class="quick-action-btn team-action" data-query="weekly start/sit {team}">Weekly</button>
                </div>
                <div class="btn-category">
                    <span class="btn-category-label">Overview:</span>
                    <button class="quick-action-btn" data-query="league overview">League</button>
                    <button class="quick-action-btn team-action" data-query="team overview {team}">Team</button>
                </div>
            </div>
            <!-- NFL quick-action buttons (shown only for NFL leagues) -->
            <div class="quick-actions" id="nfl-quick-actions" style="display: none;">
                <div class="btn-category">
                    <span class="btn-category-label">Pickups:</span>
                    <button class="quick-action-btn" data-query="weekly pickups">Weekly</button>
                    <button class="quick-action-btn" data-query="ros pickups">ROS</button>
                </div>
                <div class="btn-category">
                    <span class="btn-category-label">Start/Sit:</span>
                    <button class="quick-action-btn team-action" data-query="start sit {team}">Weekly</button>
                </div>
                <div class="btn-category">
                    <span class="btn-category-label">Overview:</span>
                    <button class="quick-action-btn" data-query="league overview">League</button>
                    <button class="quick-action-btn team-action" data-query="team overview {team}">Team</button>
                </div>
            </div>
        </div>

        <!-- Settings Modal -->
        <div id="settings-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Settings</h3>
                    <button id="close-modal-btn" class="icon-btn">✕</button>
                </div>
                <div class="modal-body">
                    <div class="setting-item">
                        <label>OpenAI API Key (Optional)</label>
                        <div class="input-group">
                            <input type="password" id="settings-api-key" placeholder="No API key - using free tier (7 messages/day)" readonly />
                            <button id="edit-api-key-btn" class="btn btn-secondary">Add/Edit</button>
                        </div>
                        <p class="setting-description">
                            ✨ Add your own API key for unlimited messages.
                            <a href="https://platform.openai.com/api-keys" target="_blank">Get one here</a>
                        </p>
                    </div>
                    <div class="setting-item">
                        <label>Message Usage</label>
                        <div id="settings-usage-info" style="padding: 10px; background: #f5f5f5; border-radius: 4px; margin-top: 5px;">
                            <div style="font-size: 14px; color: #666;">Loading...</div>
                        </div>
                    </div>
                    <div class="setting-item">
                        <label>League Data</label>
                        <button id="yahoo-connect-btn" class="btn btn-primary" style="width:100%; margin-bottom:8px; background:#6001d2; border-color:#6001d2;" onclick="window.location.href='https://valiant-healing-production-ce05.up.railway.app/api/yahoo/auth'">⚾ Connect Yahoo Fantasy League</button>
                        <div id="yahoo-status" class="status-message"></div>
                        <div style="margin-top:12px; padding-top:12px; border-top:1px solid #eee;">
                            <label style="font-weight:600; display:block; margin-bottom:6px;">⚾ Connect ESPN Fantasy League</label>
                            <p style="font-size:12px; color:#444; margin:0 0 8px; line-height:1.6;">
                                <strong>Step 1:</strong> Click <strong>Copy Code</strong> below.<br>
                                <strong>Step 2:</strong> In Chrome: press <kbd style="background:#eee;padding:1px 4px;border-radius:3px;">Ctrl+D</kbd> → <em>Edit...</em> → paste the code as the URL → Save.<br>
                                <strong>Step 3:</strong> Go to your <a href="https://fantasy.espn.com/baseball/league" target="_blank">ESPN league</a> page, click the bookmark.
                            </p>
                            <textarea id="espn-bm-code-settings" rows="2" readonly style="width:100%;font-size:10px;padding:6px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;resize:none;background:#f8f8f8;color:#333;font-family:monospace;" placeholder="Loading..."></textarea>
                            <button onclick="var t=document.getElementById('espn-bm-code-settings');t.select();document.execCommand('copy');this.textContent='Copied!';" style="width:100%;margin-top:6px;padding:8px;background:#cc0000;color:#fff;border:none;border-radius:4px;font-weight:700;cursor:pointer;font-size:13px;">Copy Code</button>
                        </div>
                        <button id="reupload-btn" class="btn btn-secondary" style="width:100%; margin-top:12px;">Upload New CSV</button>
                        <p class="setting-description">Connect your Yahoo or ESPN league, or upload a CSV from Fantrax, CBS, or NFBC</p>
                    </div>
                    <div class="setting-item">
                        <button id="clear-data-btn" class="btn btn-danger">Clear All Data</button>
                        <p class="setting-description">This will remove your API key and league data</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Loading Overlay -->
        <div id="loading-overlay" class="loading-overlay" style="display: none;">
            <div class="spinner"></div>
            <p>Processing...</p>
        </div>

    </div>
    <?php
    return ob_get_clean();
}
