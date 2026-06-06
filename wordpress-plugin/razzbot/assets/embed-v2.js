/**
 * Razzball Fantasy Baseball Chatbot - Embed Widget
 * Handles API key management, CSV upload, and chat functionality
 */

// Configuration
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000/api'
    : 'https://valiant-healing-production-ce05.up.railway.app/api';

// State management
const state = {
    apiKey: null,
    leagueId: null,
    userId: null,  // For tracking message limits
    userEmail: null,
    selectedTeam: null,  // Selected team name for quick actions
    selectedLeagueType: 'MLB12',  // Projection league type (MLB12, MLB15, etc.)
    conversationHistory: [],
    messagesRemaining: null,
    dailyLimit: 7
};

// Initialize app
document.addEventListener('DOMContentLoaded', init);

function init() {
    console.log('Razzbot initializing...');

    // Try to get user email from parent window (WordPress)
    try {
        if (window.parent !== window) {
            window.addEventListener('message', handleParentMessage);
            // Request user info from parent
            window.parent.postMessage({ type: 'REQUEST_USER_INFO' }, '*');
        }
    } catch (e) {
        console.log('Running in standalone mode');
    }

    // Handle OAuth/bookmarklet callbacks
    handleYahooCallback();
    handleESPNCallback();

    // Load saved data from localStorage
    loadSavedData();

    // Setup event listeners
    setupEventListeners();

    // Determine which screen to show
    showAppropriateScreen();
}

function handleParentMessage(event) {
    // Handle messages from parent window (WordPress)
    if (event.data.type === 'USER_INFO') {
        state.userEmail = event.data.email;
        console.log('Received user email from WordPress:', state.userEmail);
    }
}

function setupEventListeners() {
    // Setup screen buttons
    document.getElementById('save-api-key-btn')?.addEventListener('click', handleSaveApiKey);
    document.getElementById('skip-api-key-btn')?.addEventListener('click', () => {
        // Skip API key and use free tier
        showSetupScreen('upload');
    });
    document.getElementById('yahoo-connect-btn')?.addEventListener('click', handleYahooConnect);
    document.getElementById('espn-connect-btn')?.addEventListener('click', handleESPNImport);
    document.getElementById('espn-connect-btn-upload')?.addEventListener('click', handleESPNImportFromUploadScreen);
    document.getElementById('browse-btn').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });
    document.getElementById('skip-upload-btn')?.addEventListener('click', () => {
        // Skip CSV upload — user can still ask about any player by name
        showChatScreen();
    });
    document.getElementById('file-input').addEventListener('change', handleFileSelect);
    document.getElementById('start-chat-btn').addEventListener('click', () => {
        // Save team and league type selections before entering chat
        const teamSel = document.getElementById('team-selector');
        if (teamSel && teamSel.value) {
            state.selectedTeam = teamSel.value;
            localStorage.setItem('razzball_selected_team', teamSel.value);
        }
        const ltSel = document.getElementById('league-type-selector');
        if (ltSel && ltSel.value) {
            state.selectedLeagueType = ltSel.value;
            localStorage.setItem('razzball_league_type', ltSel.value);
        }
        showChatScreen();
    });

    // Chat screen buttons
    document.getElementById('send-btn').addEventListener('click', handleSendMessage);
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const tab = e.target.dataset.tab;
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tc => tc.style.display = 'none');
            // Show selected
            const tabEl = document.getElementById('tab-' + tab);
            if (tabEl) tabEl.style.display = 'flex';
            // Update active tab styling
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.style.background = '#f0f0f0';
                b.style.color = '#333';
            });
            e.target.style.background = '#1a3a5c';
            e.target.style.color = 'white';
        });
    });

    // Quick action buttons (non-tab)
    document.querySelectorAll('.quick-action-btn:not(.tab-btn)').forEach(btn => {
        btn.addEventListener('click', (e) => {
            let query = e.target.closest('.quick-action-btn').dataset.query;
            if (!query) return;

            // Replace {team} placeholder with selected team
            if (query.includes('{team}')) {
                const team = state.selectedTeam;
                if (!team) {
                    const teamName = prompt('Enter team/owner name:');
                    if (!teamName || !teamName.trim()) return;
                    query = query.replace('{team}', teamName.trim());
                } else {
                    query = query.replace('{team}', team);
                }
            }

            document.getElementById('chat-input').value = query;
            handleSendMessage();
        });
    });

    // Team selector
    document.getElementById('team-selector')?.addEventListener('change', (e) => {
        state.selectedTeam = e.target.value || null;
        if (state.selectedTeam) {
            localStorage.setItem('razzball_selected_team', state.selectedTeam);
        }
    });

    // League type selector
    document.getElementById('league-type-selector')?.addEventListener('change', (e) => {
        state.selectedLeagueType = e.target.value || 'MLB12';
        localStorage.setItem('razzball_league_type', state.selectedLeagueType);
    });

    // Settings modal
    document.getElementById('settings-btn').addEventListener('click', openSettingsModal);
    document.getElementById('close-modal-btn').addEventListener('click', closeSettingsModal);
    document.getElementById('edit-api-key-btn').addEventListener('click', () => {
        const input = document.getElementById('settings-api-key');
        input.readOnly = false;
        input.focus();
    });
    document.getElementById('reupload-btn').addEventListener('click', () => {
        closeSettingsModal();
        showSetupScreen('upload');
    });
    document.getElementById('clear-data-btn').addEventListener('click', handleClearData);

    // Drag and drop for file upload
    const uploadArea = document.getElementById('upload-area');
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('dragover');
    });
    uploadArea.addEventListener('drop', handleFileDrop);
}

function loadSavedData() {
    // Load from localStorage
    const savedApiKey = localStorage.getItem('razzball_api_key');
    const savedLeagueId = localStorage.getItem('razzball_league_id');
    let savedUserId = localStorage.getItem('razzball_user_id');

    if (savedApiKey) {
        state.apiKey = savedApiKey;
    }

    if (savedLeagueId) {
        state.leagueId = savedLeagueId;
    }

    // Generate or load user ID for message limit tracking
    // If WordPress user ID is injected by the plugin, use that so the
    // counter is tied to the WP login rather than a per-device random ID
    if (window.razzbotUserId) {
        savedUserId = window.razzbotUserId;
        localStorage.setItem('razzball_user_id', savedUserId);
    } else if (!savedUserId) {
        savedUserId = generateUserId();
        localStorage.setItem('razzball_user_id', savedUserId);
    }
    state.userId = savedUserId;

    // Load saved league type
    const savedLeagueType = localStorage.getItem('razzball_league_type');
    if (savedLeagueType) {
        state.selectedLeagueType = savedLeagueType;
        const ltSelector = document.getElementById('league-type-selector');
        if (ltSelector) ltSelector.value = savedLeagueType;
    }

    // Load saved team selection
    const savedTeam = localStorage.getItem('razzball_selected_team');
    if (savedTeam) {
        state.selectedTeam = savedTeam;
    }
}

async function showAppropriateScreen() {
    if (state.leagueId) {
        if (state.selectedTeam) {
            // Has league + team selected - go straight to chat
            showChatScreen();
        } else {
            // Has league but no team - show team selector, wait for teams to load first
            showSetupScreen('ready');
            await loadTeamsForSelector();
        }
    } else {
        // No league data - show upload (API key is now optional)
        showSetupScreen('upload');
    }
}

function showSetupScreen(step = 'api-key') {
    document.getElementById('setup-screen').classList.add('active');
    document.getElementById('chat-screen').classList.remove('active');

    // Show the appropriate step
    const steps = {
        'api-key': document.getElementById('step-api-key'),
        'upload': document.getElementById('step-upload'),
        'ready': document.getElementById('step-ready')
    };

    Object.values(steps).forEach(s => s.style.display = 'none');
    steps[step].style.display = 'block';
}

function showChatScreen() {
    document.getElementById('setup-screen').classList.remove('active');
    document.getElementById('chat-screen').classList.add('active');
    document.getElementById('chat-input').focus();

    // Initialize message counter display
    if (state.apiKey) {
        updateMessageCounter(null); // Unlimited
    } else {
        updateMessageCounter(state.messagesRemaining || state.dailyLimit); // Show default or saved value
    }
}

function populateTeamSelector(teams) {
    const selector = document.getElementById('team-selector');
    if (!selector) return;

    // Clear existing options (keep the default)
    selector.innerHTML = '<option value="">-- Select your team --</option>';

    teams.forEach(team => {
        const opt = document.createElement('option');
        opt.value = team;
        opt.textContent = team;
        // Pre-select if previously saved
        if (state.selectedTeam === team) {
            opt.selected = true;
        }
        selector.appendChild(opt);
    });
}

async function loadTeamsForSelector() {
    if (!state.leagueId) return;
    try {
        const response = await fetch(`${API_BASE_URL}/csv/${state.leagueId}/teams`);
        if (response.ok) {
            const data = await response.json();
            if (data.teams && data.teams.length > 0) {
                populateTeamSelector(data.teams);
            } else {
                // League data was cleared (server restart/redeploy wiped the DB)
                state.leagueId = null;
                localStorage.removeItem('razzball_league_id');
                localStorage.removeItem('razzball_selected_team');
                showSetupScreen('upload');
                showStatus(
                    document.getElementById('upload-status'),
                    'ℹ️ League data was cleared by a server update. Please re-upload your CSV.',
                    'info'
                );
            }
        } else {
            // League not found (404) — stale leagueId
            state.leagueId = null;
            localStorage.removeItem('razzball_league_id');
            localStorage.removeItem('razzball_selected_team');
            showSetupScreen('upload');
            showStatus(
                document.getElementById('upload-status'),
                'ℹ️ League data was cleared by a server update. Please re-upload your CSV.',
                'info'
            );
        }
    } catch (e) {
        console.warn('Could not fetch teams:', e);
        // Network error — don't clear, could be temporary
    }
}

// API Key Management
async function handleSaveApiKey() {
    const input = document.getElementById('api-key-input');
    const apiKey = input.value.trim();
    const statusEl = document.getElementById('api-key-status');

    if (!apiKey || !apiKey.startsWith('sk-')) {
        showStatus(statusEl, 'Please enter a valid OpenAI API key (starts with sk-)', 'error');
        return;
    }

    // Save API key
    state.apiKey = apiKey;
    localStorage.setItem('razzball_api_key', apiKey);

    // Show success and move to next step
    showStatus(statusEl, 'API key saved successfully!', 'success');

    setTimeout(() => {
        if (state.leagueId) {
            showSetupScreen('ready');
        } else {
            showSetupScreen('upload');
        }
    }, 1000);
}

// File Upload
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        uploadFile(file);
    }
}

function handleFileDrop(event) {
    event.preventDefault();
    document.getElementById('upload-area').classList.remove('dragover');

    const file = event.dataTransfer.files[0];
    const allowed = ['.csv', '.xls', '.xlsx'];
    if (file && allowed.some(ext => file.name.toLowerCase().endsWith(ext))) {
        uploadFile(file);
    } else {
        showStatus(document.getElementById('upload-status'), 'Please upload a CSV or Excel file', 'error');
    }
}

async function uploadFile(file) {
    const statusEl = document.getElementById('upload-status');
    showStatus(statusEl, 'Uploading and processing your league file...', 'info');
    showLoading(true);

    try {
        const formData = new FormData();
        formData.append('file', file);
        if (state.leagueId) formData.append('existing_league_id', state.leagueId);

        // Detect league type from filename
        const filename = file.name.toLowerCase();
        let leagueType = 'fantrax';  // default
        if (filename.includes('cbs')) leagueType = 'cbs';
        if (filename.includes('nfbc')) leagueType = 'nfbc';

        formData.append('league_type', leagueType);

        const response = await fetch(`${API_BASE_URL}/csv/upload`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            let errMsg = 'Upload failed';
            try { const errData = await response.json(); errMsg = errData.detail || errMsg; } catch {}
            throw new Error(errMsg);
        }

        const data = await response.json();

        // Save league ID and clear stale team selection from previous upload
        state.leagueId = data.id;
        state.selectedTeam = null;
        localStorage.setItem('razzball_league_id', data.id);
        localStorage.removeItem('razzball_selected_team');

        showStatus(statusEl, `✅ Success! Loaded ${data.total_players} players from your league`, 'success');

        // Populate teams immediately from upload response (eliminates race condition)
        if (data.teams && data.teams.length > 0) {
            populateTeamSelector(data.teams);
        }

        setTimeout(() => {
            showSetupScreen('ready');
            // Restore league type selector to saved value
            const ltSelector = document.getElementById('league-type-selector');
            if (ltSelector) ltSelector.value = state.selectedLeagueType;
        }, 1500);

    } catch (error) {
        console.error('Upload error:', error);
        showStatus(statusEl, `Failed to upload: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// Yahoo Fantasy OAuth
function handleYahooConnect() {
    // Redirect to Yahoo OAuth flow
    window.location.href = `${API_BASE_URL}/yahoo/auth`;
}

async function handleYahooCallback() {
    const params = new URLSearchParams(window.location.search);
    const tokenParam = params.get('yahoo_token');
    const leaguesParam = params.get('yahoo_leagues');

    if (!tokenParam) return;

    // Remove params from URL without reload
    const cleanUrl = window.location.pathname;
    window.history.replaceState({}, document.title, cleanUrl);

    const [accessToken, refreshToken] = atob(tokenParam).split(':');
    const leagueKeys = leaguesParam ? leaguesParam.split(',').filter(Boolean) : [];

    const statusEl = document.getElementById('yahoo-status');
    showSetupScreen('upload');

    if (!leagueKeys.length) {
        showStatus(statusEl, 'No Yahoo MLB leagues found for your account.', 'error');
        return;
    }

    // If multiple leagues, use the first one (can add picker later)
    const leagueKey = leagueKeys[0];
    showStatus(statusEl, `Importing Yahoo league ${leagueKey}...`, 'info');
    showLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/yahoo/import-league`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                league_key: leagueKey,
                access_token: accessToken,
                refresh_token: refreshToken,
                existing_league_id: state.leagueId || null,
            })
        });

        if (!response.ok) {
            let errMsg = 'Import failed';
            try { const e = await response.json(); errMsg = e.detail || errMsg; } catch {}
            throw new Error(errMsg);
        }

        const data = await response.json();
        state.leagueId = data.id;
        state.selectedTeam = null;
        localStorage.setItem('razzball_league_id', data.id);
        localStorage.setItem('razzball_yahoo_token', accessToken);
        localStorage.setItem('razzball_yahoo_refresh', data.refresh_token || refreshToken);
        localStorage.removeItem('razzball_selected_team');

        showStatus(statusEl, `✅ Yahoo league loaded! ${data.owned_players} players across ${data.teams.length} teams.`, 'success');

        if (data.teams && data.teams.length > 0) {
            populateTeamSelector(data.teams);
        }

        setTimeout(() => {
            showSetupScreen('ready');
            const ltSelector = document.getElementById('league-type-selector');
            if (ltSelector) ltSelector.value = state.selectedLeagueType;
        }, 1500);

    } catch (error) {
        console.error('Yahoo import error:', error);
        showStatus(statusEl, `Failed to import Yahoo league: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// ESPN bookmarklet callback — fired when the bookmarklet redirects back with ?espn_league=<id>
function handleESPNCallback() {
    const params = new URLSearchParams(window.location.search);
    const leagueId = params.get('espn_league');
    if (!leagueId) return;

    // Clean the URL
    window.history.replaceState({}, document.title, window.location.pathname);

    state.leagueId = leagueId;
    state.selectedTeam = null;
    localStorage.setItem('razzball_league_id', leagueId);
    localStorage.removeItem('razzball_selected_team');

    showSetupScreen('upload');
    const statusEl = document.getElementById('upload-status');
    if (statusEl) showStatus(statusEl, 'ESPN league connected! Now choose your team below.', 'success');

    // Fetch team list from the saved league so we can populate the selector
    fetch(`${API_BASE_URL}/csv/${leagueId}/teams`)
        .then(r => r.ok ? r.json() : null)
        .then(data => {
            if (data && data.teams && data.teams.length > 0) {
                populateTeamSelector(data.teams);
            }
            setTimeout(() => {
                showSetupScreen('ready');
                const ltSelector = document.getElementById('league-type-selector');
                if (ltSelector) ltSelector.value = state.selectedLeagueType;
            }, 1000);
        })
        .catch(() => {
            setTimeout(() => showSetupScreen('ready'), 1000);
        });
}

// ESPN Fantasy
async function handleESPNImportFromUploadScreen() {}
async function handleESPNImport() {}

const ESPN_POSITION_MAP = {1:'C',2:'1B',3:'2B',4:'3B',5:'SS',6:'OF',7:'DH',8:'SP',9:'RP'};
const ESPN_TEAM_MAP = {
    1:'ATL',2:'BOS',3:'LAA',4:'CWS',5:'CLE',6:'COL',7:'DET',8:'HOU',9:'KC',10:'MIL',
    11:'MIN',12:'NYM',13:'NYY',14:'OAK',15:'PHI',16:'PIT',17:'STL',18:'SD',19:'SF',
    20:'SEA',21:'TB',22:'TEX',23:'TOR',24:'WSH',25:'ATH',26:'CIN',27:'LAD',28:'ARI',
    29:'CHC',30:'MIA'
};
const ESPN_IL_SLOTS = new Set([17]);

function parseESPNResponse(data) {
    const teams = data.teams || [];
    const teamNameMap = {};
    for (const t of teams) {
        teamNameMap[t.id] = (t.name || t.abbrev || `Team ${t.id}`).trim();
    }
    const players = [];
    for (const team of teams) {
        const ownerName = teamNameMap[team.id];
        for (const entry of (team.roster?.entries || [])) {
            const lineupSlot = entry.lineupSlotId || 0;
            const player = entry.playerPoolEntry?.player || {};
            const playerName = (player.fullName || '').trim();
            if (!playerName) continue;
            players.push({
                name: playerName,
                team: ESPN_TEAM_MAP[player.proTeamId] || '',
                position: ESPN_POSITION_MAP[player.defaultPositionId] || 'UTIL',
                owner: ownerName,
                status: ESPN_IL_SLOTS.has(lineupSlot) ? 'IL' : null
            });
        }
    }
    const leagueName = data.settings?.name || '';
    const teamNames = [...new Set(players.map(p => p.owner))].sort();
    return { players, leagueName, teamNames };
}

async function _doESPNImport(leagueId, espnS2, swid, statusEl) {
    if (!leagueId) {
        if (statusEl) showStatus(statusEl, 'Please enter your ESPN League ID.', 'error');
        return;
    }

    if (statusEl) showStatus(statusEl, 'Connecting to ESPN...', 'info');
    showLoading(true);

    try {
        // Call ESPN directly from the browser (avoids Railway IP blocks).
        // Cookies are sent automatically via credentials:'include' if the
        // user is already logged into ESPN in this browser.
        const espnUrl = `https://fantasy.espn.com/apis/v3/games/flb/seasons/2026/segments/0/leagues/${leagueId}?view=mRoster&view=mTeam&view=mSettings`;
        console.log('[ESPN] Fetching from browser:', espnUrl);

        let espnData;
        try {
            const espnResp = await fetch(espnUrl, {
                credentials: 'include',
                headers: { 'Accept': 'application/json' }
            });
            if (espnResp.status === 401) throw new Error('ESPN auth failed — make sure you are logged into ESPN in this browser.');
            if (espnResp.status === 404) throw new Error('ESPN league not found — check your League ID.');
            if (!espnResp.ok) throw new Error(`ESPN returned ${espnResp.status}`);
            espnData = await espnResp.json();
        } catch (espnErr) {
            if (espnErr.message.startsWith('ESPN')) throw espnErr;
            // Network/CORS error
            throw new Error('Could not reach ESPN from your browser. Make sure you are logged into ESPN.com in this tab, then try again.');
        }

        console.log('[ESPN] Got ESPN data, parsing...');
        const { players, leagueName, teamNames } = parseESPNResponse(espnData);
        console.log('[ESPN] Parsed', players.length, 'players across', teamNames.length, 'teams');

        if (players.length === 0) throw new Error('No players found. Check that your League ID is correct and the league has rosters set.');

        // Post parsed players to Railway (our own server — no IP blocks)
        const response = await fetch(`${API_BASE_URL}/espn/import-parsed`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                players,
                league_name: leagueName,
                espn_league_id: leagueId,
                existing_league_id: state.leagueId || null
            })
        });

        if (!response.ok) {
            let errMsg = 'Save failed';
            try { const e = await response.json(); errMsg = e.detail || errMsg; } catch {}
            throw new Error(errMsg);
        }

        const data = await response.json();
        state.leagueId = data.id;
        state.selectedTeam = null;
        localStorage.setItem('razzball_league_id', data.id);
        localStorage.removeItem('razzball_selected_team');

        const uploadStatusEl = document.getElementById('upload-status');
        const msg = `ESPN league loaded! ${players.length} players across ${teamNames.length} teams.`;
        if (uploadStatusEl) showStatus(uploadStatusEl, msg, 'success');
        if (statusEl && statusEl !== uploadStatusEl) showStatus(statusEl, msg, 'success');

        if (teamNames.length > 0) populateTeamSelector(teamNames);

        setTimeout(() => {
            showSetupScreen('ready');
            const ltSelector = document.getElementById('league-type-selector');
            if (ltSelector) ltSelector.value = state.selectedLeagueType;
        }, 1500);

    } catch (error) {
        console.error('[ESPN] Import error:', error);
        const msg = error.message || 'Unknown error';
        if (statusEl) showStatus(statusEl, `ESPN import failed: ${msg}`, 'error');
        const uploadStatusEl = document.getElementById('upload-status');
        if (uploadStatusEl && statusEl !== uploadStatusEl) showStatus(uploadStatusEl, `ESPN import failed: ${msg}`, 'error');
    } finally {
        showLoading(false);
    }
}

// Chat Functionality
async function handleSendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    // Clear input
    input.value = '';

    // Add user message to chat
    addMessageToChat(message, 'user');

    // Show loading state
    setLoadingState(true);

    try {
        const response = await fetch(`${API_BASE_URL}/chat/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                league_id: state.leagueId,
                user_id: state.userId,
                user_api_key: state.apiKey || null,  // Optional - backend will use its key if null
                provider: 'openai',
                league_type: state.selectedLeagueType || 'MLB12',
                conversation_history: state.conversationHistory.slice(-6)  // Send last 6 messages for memory
            })
        });

        if (response.status === 429) {
            // Message limit reached
            const errorData = await response.json();
            const detail = errorData.detail;
            addMessageToChat(
                `⚠️ ${detail.message || 'Daily message limit reached'}\n\n` +
                `Your limit will reset at ${new Date(detail.reset_date).toLocaleString()}.\n\n` +
                `Want unlimited messages? Add your own OpenAI API key in Settings (⚙️).`,
                'bot'
            );
            updateMessageCounter(0);
            setLoadingState(false);
            input.focus();
            return;
        }

        if (response.status === 404) {
            // League data was lost (server restart wiped the DB) — clear stale ID and prompt re-upload
            state.leagueId = null;
            state.selectedTeam = null;
            localStorage.removeItem('razzball_league_id');
            localStorage.removeItem('razzball_selected_team');
            setLoadingState(false);
            showSetupScreen('upload');
            showStatus(
                document.getElementById('upload-status'),
                'ℹ️ Your league data was cleared by a server update. Please re-upload your CSV.',
                'info'
            );
            return;
        }

        if (!response.ok) {
            throw new Error('Chat request failed');
        }

        const data = await response.json();

        // Add bot response to chat
        addMessageToChat(data.response, 'bot');

        // Update message counter if we have the info
        if (data.messages_remaining !== undefined) {
            updateMessageCounter(data.messages_remaining);
        }

        // Update conversation history
        state.conversationHistory.push(
            { role: 'user', content: message },
            { role: 'assistant', content: data.response }
        );

    } catch (error) {
        console.error('Chat error:', error);
        addMessageToChat(
            'Sorry, I encountered an error. Please try again.',
            'bot'
        );
    } finally {
        setLoadingState(false);
        input.focus();
    }
}

function addMessageToChat(text, type) {
    const messagesContainer = document.getElementById('chat-messages');

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Convert markdown-style tables and formatting
    const formattedText = formatMessage(text);
    contentDiv.innerHTML = formattedText;

    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function formatMessage(text) {
    // Convert markdown to HTML (simple version)
    let formatted = text;

    // Convert **bold** to <strong>
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Convert *italic* to <em>
    formatted = formatted.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Convert line breaks
    formatted = formatted.replace(/\n/g, '<br>');

    // Convert markdown tables (basic)
    if (formatted.includes('|')) {
        formatted = convertMarkdownTable(formatted);
    }

    return formatted;
}

function convertMarkdownTable(text) {
    const lines = text.split('<br>');
    let inTable = false;
    let tableHTML = '';
    let result = '';

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();

        if (line.startsWith('|') && line.endsWith('|')) {
            if (!inTable) {
                inTable = true;
                tableHTML = '<table><thead><tr>';

                // Header row — preserve all columns including empty ones
                const allHeaders = line.split('|');
                const headers = allHeaders.slice(
                    allHeaders[0].trim() === '' ? 1 : 0,
                    allHeaders[allHeaders.length - 1].trim() === '' ? allHeaders.length - 1 : allHeaders.length
                );
                headers.forEach(header => {
                    tableHTML += `<th>${header.trim()}</th>`;
                });
                tableHTML += '</tr></thead><tbody>';

                // Skip separator line
                i++;
                continue;
            } else {
                // Data row — split then remove only the leading/trailing empty slots
                const allCells = line.split('|');
                // Drop first and last empty strings (from leading/trailing |)
                const cells = allCells.slice(
                    allCells[0].trim() === '' ? 1 : 0,
                    allCells[allCells.length - 1].trim() === '' ? allCells.length - 1 : allCells.length
                );
                tableHTML += '<tr>';
                cells.forEach(cell => {
                    const val = cell.trim();
                    const isNumeric = /^-?[\d.]+$/.test(val);
                    const align = isNumeric ? ' style="text-align:right"' : '';
                    tableHTML += `<td${align}>${val}</td>`;
                });
                tableHTML += '</tr>';
            }
        } else if (inTable) {
            // End of table
            inTable = false;
            tableHTML += '</tbody></table>';
            result += tableHTML + '<br>';
            tableHTML = '';
            result += line + '<br>';
        } else {
            result += line + '<br>';
        }
    }

    if (inTable) {
        tableHTML += '</tbody></table>';
        result += tableHTML;
    }

    return result;
}

function setLoadingState(loading) {
    const sendBtn = document.getElementById('send-btn');
    const sendIcon = document.getElementById('send-icon');
    const loadingIcon = document.getElementById('loading-icon');
    const input = document.getElementById('chat-input');

    if (loading) {
        sendBtn.disabled = true;
        sendIcon.style.display = 'none';
        loadingIcon.style.display = 'inline';
        input.disabled = true;
    } else {
        sendBtn.disabled = false;
        sendIcon.style.display = 'inline';
        loadingIcon.style.display = 'none';
        input.disabled = false;
    }
}

// Settings Modal
function openSettingsModal() {
    document.getElementById('settings-modal').classList.add('active');

    // Load current API key (masked)
    const apiKeyInput = document.getElementById('settings-api-key');
    if (state.apiKey) {
        apiKeyInput.value = state.apiKey.substring(0, 10) + '...' + state.apiKey.substring(state.apiKey.length - 4);
        apiKeyInput.placeholder = '';
        apiKeyInput.readOnly = true;
    } else {
        apiKeyInput.value = '';
        apiKeyInput.placeholder = 'No API key - using free tier (7 messages/day)';
    }

    // Display usage information
    const usageInfo = document.getElementById('settings-usage-info');
    if (state.apiKey) {
        usageInfo.innerHTML = '<div style="font-size: 14px; color: #27ae60; font-weight: 600;">✨ Unlimited messages (using your API key)</div>';
    } else {
        const remaining = state.messagesRemaining !== null ? state.messagesRemaining : state.dailyLimit;
        const used = state.dailyLimit - remaining;
        const percentage = (used / state.dailyLimit * 100).toFixed(0);
        const color = remaining <= 1 ? '#e74c3c' : (remaining <= 3 ? '#f39c12' : '#27ae60');

        usageInfo.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: #666;">Used today:</span>
                <strong>${used} / ${state.dailyLimit}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: #666;">Remaining:</span>
                <strong style="color: ${color}">${remaining} messages</strong>
            </div>
            <div style="width: 100%; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; margin-top: 10px;">
                <div style="width: ${percentage}%; height: 100%; background: ${color}; transition: width 0.3s;"></div>
            </div>
        `;
    }
}

function closeSettingsModal() {
    document.getElementById('settings-modal').classList.remove('active');

    // Save any changes to API key
    const apiKeyInput = document.getElementById('settings-api-key');
    if (!apiKeyInput.readOnly && apiKeyInput.value.startsWith('sk-')) {
        state.apiKey = apiKeyInput.value;
        localStorage.setItem('razzball_api_key', apiKeyInput.value);
        // Update message counter to show unlimited
        updateMessageCounter(null);
    }
}

function handleClearData() {
    if (confirm('Are you sure you want to clear all data? You will need to re-enter your API key and re-upload your league file.')) {
        // Clear state
        state.apiKey = null;
        state.leagueId = null;
        state.conversationHistory = [];

        // Clear localStorage
        localStorage.removeItem('razzball_api_key');
        localStorage.removeItem('razzball_league_id');
        localStorage.removeItem('razzball_selected_team');
        localStorage.removeItem('razzball_league_type');

        // Close modal and go back to setup
        closeSettingsModal();
        showSetupScreen('api-key');
    }
}

// Utility Functions
function showStatus(element, message, type) {
    element.textContent = message;
    element.className = `status-message ${type}`;
}

function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    overlay.style.display = show ? 'flex' : 'none';
}

function generateUserId() {
    // Generate a unique user ID (UUID v4)
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function updateMessageCounter(remaining) {
    state.messagesRemaining = remaining;

    // Update UI if counter element exists
    const counterEl = document.getElementById('message-counter');
    if (counterEl) {
        if (state.apiKey) {
            // User has their own API key - unlimited
            counterEl.innerHTML = '<span style="color: #27ae60;">✨ Unlimited messages</span>';
        } else {
            // Using backend key - show remaining
            const color = remaining <= 10 ? '#e74c3c' : (remaining <= 30 ? '#f39c12' : '#27ae60');
            counterEl.innerHTML = `<span style="color: ${color};">${remaining} messages remaining today</span>`;
        }
        counterEl.style.display = 'block';
    }
}

// Export for parent window access
window.RazzballChatbot = {
    setUserEmail: (email) => {
        state.userEmail = email;
    },
    reset: () => {
        handleClearData();
    }
};

// Expose ESPN/Yahoo handlers to global scope for inline onclick attributes
window.handleESPNImport = handleESPNImport;
window.handleESPNImportFromUploadScreen = handleESPNImportFromUploadScreen;
window.handleYahooConnect = handleYahooConnect;

console.log('Razzbot loaded successfully');
