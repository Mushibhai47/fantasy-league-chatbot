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

define( 'RAZZBOT_VERSION',    '1.0.5' );
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
function razzball_chatbot_shortcode() {
    $bookmarklet = "javascript:(function(){var P={1:'C',2:'1B',3:'2B',4:'3B',5:'SS',6:'OF',7:'DH',8:'SP',9:'RP'};var T={1:'ATL',2:'BOS',3:'LAA',4:'CWS',5:'CLE',6:'COL',7:'DET',8:'HOU',9:'KC',10:'MIL',11:'MIN',12:'NYM',13:'NYY',14:'OAK',15:'PHI',16:'PIT',17:'STL',18:'SD',19:'SF',20:'SEA',21:'TB',22:'TEX',23:'TOR',24:'WSH',25:'ATH',26:'CIN',27:'LAD',28:'ARI',29:'CHC',30:'MIA'};var m=location.href.match(/leagueId=(\d+)/);if(!m){alert('Go to your ESPN Fantasy Baseball league page first, then click this bookmark.');return;}var lid=m[1];fetch('https://fantasy.espn.com/apis/v3/games/flb/seasons/2026/segments/0/leagues/'+lid+'?view=mRoster&view=mTeam&view=mSettings',{credentials:'include',headers:{Accept:'application/json'}}).then(function(r){if(!r.ok)throw new Error('ESPN error '+r.status+'. Are you logged into ESPN?');return r.json();}).then(function(d){var nm={};(d.teams||[]).forEach(function(t){nm[t.id]=(t.name||t.abbrev||'Team '+t.id).trim();});var pl=[];(d.teams||[]).forEach(function(t){(t.roster&&t.roster.entries||[]).forEach(function(e){var p=(e.playerPoolEntry&&e.playerPoolEntry.player)||{};var n=(p.fullName||'').trim();if(!n)return;pl.push({name:n,team:T[p.proTeamId]||'',position:P[p.defaultPositionId]||'UTIL',owner:nm[t.id],status:e.lineupSlotId===17?'IL':null});});});return fetch('https://valiant-healing-production-ce05.up.railway.app/api/espn/import-parsed',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({players:pl,league_name:(d.settings&&d.settings.name)||'',espn_league_id:lid})});}).then(function(r){if(!r.ok)throw new Error('Save failed: '+r.status);return r.json();}).then(function(res){location.href='https://razzball.com/rotodeluxe/?espn_league='+res.id;}).catch(function(e){alert('Razzbot ESPN: '+e.message);});})();";
    ob_start();
    ?>
    <div id="razzball-chatbot-embed">

        <!-- Setup Screen (first time users) -->
        <div id="setup-screen" class="screen active">
            <div class="setup-container">
                <div class="logo-section">
                    <h1>Razzbot</h1>
                    <p>The Fantasy Baseball Assistant by Razzball</p>
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
                    <p class="step-description">Connect your Yahoo or ESPN league, or upload a CSV from Fantrax, CBS, or NFBC</p>

                    <div id="yahoo-status" class="status-message"></div>

                    <button id="yahoo-connect-btn-upload" class="btn btn-primary" style="width:100%; margin-bottom:8px; background:#6001d2; border-color:#6001d2;" onclick="window.location.href='https://valiant-healing-production-ce05.up.railway.app/api/yahoo/auth'">⚾ Connect Yahoo Fantasy League</button>

                    <?php /* ESPN bookmarklet UI — $bookmarklet defined at top of function */ ?>
                    <div style="margin-bottom:12px; padding:12px; border:1px solid #eee; border-radius:6px; background:#fafafa;">
                        <label style="font-weight:600; display:block; margin-bottom:6px; font-size:13px;">⚾ Connect ESPN Fantasy League</label>
                        <p style="font-size:12px; color:#444; margin:0 0 10px; line-height:1.5;">
                            <strong>Step 1:</strong> Drag the button below to your bookmarks bar.<br>
                            <strong>Step 2:</strong> Go to your <a href="https://fantasy.espn.com/baseball/league" target="_blank">ESPN Fantasy Baseball league</a> page.<br>
                            <strong>Step 3:</strong> Click the bookmark — it will import your league and bring you back here.
                        </p>
                        <div style="text-align:center; margin:10px 0;">
                            <a href="<?php echo esc_attr( $bookmarklet ); ?>"
                               style="display:inline-block; padding:10px 20px; background:#cc0000; color:#fff; font-weight:700; font-size:14px; border-radius:6px; text-decoration:none; border:2px dashed #fff; box-shadow:0 0 0 2px #cc0000; cursor:grab;"
                               onclick="event.preventDefault(); alert('Drag this button to your bookmarks bar, then use it on your ESPN league page.');">
                                ⚾ Razzbot ESPN Importer
                            </a>
                        </div>
                        <p style="font-size:11px; color:#888; text-align:center; margin:6px 0 0;">Drag the red button above to your bookmarks bar</p>
                    </div>

                    <p style="text-align:center; font-size:13px; color:#888; margin:8px 0;">or upload a CSV</p>

                    <div class="upload-area" id="upload-area">
                        <div class="upload-icon">📄</div>
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
                    <div class="input-group" style="margin-bottom: 16px;">
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
                        <p>Welcome to Razzbot! Load your team by clicking the Settings button. Use the full league export from NFBC, Fantrax, or CBSSports (where you'll have to combine hitters and pitchers downloads). Use the one where you see league owner next to the player. (We have a link at <a href="https://razzball.com/rotodeluxe" target="_blank">razzball.com/rotodeluxe</a> if you need help.)</p>
                        <p>You then choose your Team name and closest League format then press the buttons at the bottom to get a <strong>League Overview</strong> based on our ROS player rater, a <strong>Team Overview</strong> (type in Team Overview &lt;owner name&gt; if you are reviewing other teams), and Today/Tomorrow/Weekly pickups and start/sit (all your current players).</p>
                    </div>
                </div>
            </div>

            <div class="chat-input-container">
                <textarea id="chat-input" placeholder="Ask me anything about your fantasy baseball team..." rows="2"></textarea>
                <button id="send-btn" class="btn btn-primary">
                    <span id="send-icon">Send</span>
                    <span id="loading-icon" style="display: none;">●●●</span>
                </button>
            </div>

            <div id="message-counter" style="display: none; text-align: center; padding: 8px; font-size: 13px; color: #666;"></div>

            <div class="quick-actions">
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
                            <p style="font-size:12px; color:#444; margin:0 0 10px; line-height:1.5;">
                                <strong>Step 1:</strong> Drag the button below to your bookmarks bar.<br>
                                <strong>Step 2:</strong> Go to your <a href="https://fantasy.espn.com/baseball/league" target="_blank">ESPN Fantasy Baseball league</a> page.<br>
                                <strong>Step 3:</strong> Click the bookmark to import and return here.
                            </p>
                            <div style="text-align:center; margin:10px 0;">
                                <a href="<?php echo esc_attr( $bookmarklet ); ?>"
                                   style="display:inline-block; padding:10px 20px; background:#cc0000; color:#fff; font-weight:700; font-size:14px; border-radius:6px; text-decoration:none; border:2px dashed #fff; box-shadow:0 0 0 2px #cc0000; cursor:grab;"
                                   onclick="event.preventDefault(); alert('Drag this button to your bookmarks bar, then use it on your ESPN league page.');">
                                    ⚾ Razzbot ESPN Importer
                                </a>
                            </div>
                            <p style="font-size:11px; color:#888; text-align:center; margin:6px 0 0;">Drag the red button to your bookmarks bar</p>
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
