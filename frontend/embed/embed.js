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
    conversationHistory: [],
    messagesRemaining: null,
    monthlyLimit: 100
};

// Initialize app
document.addEventListener('DOMContentLoaded', init);

function init() {
    console.log('Razzball Chatbot Embed initializing...');

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
    document.getElementById('browse-btn').addEventListener('click', () => {
        document.getElementById('file-input').click();
    });
    document.getElementById('file-input').addEventListener('change', handleFileSelect);
    document.getElementById('start-chat-btn').addEventListener('click', showChatScreen);

    // Chat screen buttons
    document.getElementById('send-btn').addEventListener('click', handleSendMessage);
    document.getElementById('chat-input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // Quick action buttons
    document.querySelectorAll('.quick-action-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const query = e.target.dataset.query;
            document.getElementById('chat-input').value = query;
            handleSendMessage();
        });
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
    if (!savedUserId) {
        savedUserId = generateUserId();
        localStorage.setItem('razzball_user_id', savedUserId);
    }
    state.userId = savedUserId;
}

function showAppropriateScreen() {
    if (state.leagueId) {
        // Has league data - go straight to chat
        showChatScreen();
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
        updateMessageCounter(state.messagesRemaining || state.monthlyLimit); // Show default or saved value
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
    if (file && file.name.endsWith('.csv')) {
        uploadFile(file);
    } else {
        showStatus(document.getElementById('upload-status'), 'Please upload a CSV file', 'error');
    }
}

async function uploadFile(file) {
    const statusEl = document.getElementById('upload-status');
    showStatus(statusEl, 'Uploading and processing your league file...', 'info');
    showLoading(true);

    try {
        const formData = new FormData();
        formData.append('file', file);

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
            throw new Error('Upload failed');
        }

        const data = await response.json();

        // Save league ID
        state.leagueId = data.id;
        localStorage.setItem('razzball_league_id', data.id);

        showStatus(statusEl, `✅ Success! Loaded ${data.total_players} players from your league`, 'success');

        setTimeout(() => {
            showSetupScreen('ready');
        }, 1500);

    } catch (error) {
        console.error('Upload error:', error);
        showStatus(statusEl, 'Failed to upload file. Please try again.', 'error');
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
                conversation_history: state.conversationHistory.slice(-6)  // Send last 6 messages for memory
            })
        });

        if (response.status === 429) {
            // Message limit reached
            const errorData = await response.json();
            const detail = errorData.detail;
            addMessageToChat(
                `⚠️ ${detail.message || 'Monthly message limit reached'}\n\n` +
                `Your limit will reset on ${new Date(detail.reset_date).toLocaleDateString()}.\n\n` +
                `Want unlimited messages? Add your own OpenAI API key in Settings (⚙️).`,
                'bot'
            );
            updateMessageCounter(0);
            setLoadingState(false);
            input.focus();
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

                // Header row
                const headers = line.split('|').filter(h => h.trim());
                headers.forEach(header => {
                    tableHTML += `<th>${header.trim()}</th>`;
                });
                tableHTML += '</tr></thead><tbody>';

                // Skip separator line
                i++;
                continue;
            } else {
                // Data row
                const cells = line.split('|').filter(c => c.trim());
                tableHTML += '<tr>';
                cells.forEach(cell => {
                    tableHTML += `<td>${cell.trim()}</td>`;
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
        apiKeyInput.placeholder = 'No API key - using free tier (100 messages/month)';
    }

    // Display usage information
    const usageInfo = document.getElementById('settings-usage-info');
    if (state.apiKey) {
        usageInfo.innerHTML = '<div style="font-size: 14px; color: #27ae60; font-weight: 600;">✨ Unlimited messages (using your API key)</div>';
    } else {
        const remaining = state.messagesRemaining !== null ? state.messagesRemaining : state.monthlyLimit;
        const used = state.monthlyLimit - remaining;
        const percentage = (used / state.monthlyLimit * 100).toFixed(0);
        const color = remaining <= 10 ? '#e74c3c' : (remaining <= 30 ? '#f39c12' : '#27ae60');

        usageInfo.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <span style="color: #666;">Used this month:</span>
                <strong>${used} / ${state.monthlyLimit}</strong>
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
            counterEl.innerHTML = `<span style="color: ${color};">${remaining} messages remaining this month</span>`;
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

console.log('Razzball Chatbot Embed loaded successfully');
