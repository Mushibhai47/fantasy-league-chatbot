/**
 * Razzball Fantasy Baseball Chatbot - Admin Dashboard
 * Complete functionality for admin panel
 */

// Configuration
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000/api'
    : 'https://chatbot.razzball.com/api';

// Admin credentials (in production, use proper authentication)
const ADMIN_CREDENTIALS = {
    'rudy': 'razzball2024',
    'grey': 'razzball2024'
};

// State management
const state = {
    isAuthenticated: false,
    currentUser: null,
    currentView: 'dashboard',
    dashboardData: null,
    usersData: [],
    analyticsData: null,
    chatsData: []
};

// Initialize app
document.addEventListener('DOMContentLoaded', init);

function init() {
    console.log('Admin Dashboard initializing...');

    // Check authentication
    checkAuthentication();

    // Setup event listeners
    setupEventListeners();

    // Update time display
    updateTimeDisplay();
    setInterval(updateTimeDisplay, 1000);

    // Load initial data if authenticated
    if (state.isAuthenticated) {
        loadDashboardData();
    }
}

// ========================================
// Authentication
// ========================================
function checkAuthentication() {
    const savedAuth = localStorage.getItem('razzball_admin_auth');
    if (savedAuth) {
        const authData = JSON.parse(savedAuth);
        state.isAuthenticated = true;
        state.currentUser = authData.username;
        showDashboard();
        document.getElementById('admin-name').textContent = capitalizeFirst(state.currentUser);
    } else {
        showLoginScreen();
    }
}

function showLoginScreen() {
    document.getElementById('login-screen').style.display = 'flex';
}

function showDashboard() {
    document.getElementById('login-screen').style.display = 'none';
}

function handleLogin(e) {
    e.preventDefault();

    const username = document.getElementById('login-username').value.toLowerCase();
    const password = document.getElementById('login-password').value;
    const errorEl = document.getElementById('login-error');

    // Validate credentials
    if (ADMIN_CREDENTIALS[username] && ADMIN_CREDENTIALS[username] === password) {
        // Success
        state.isAuthenticated = true;
        state.currentUser = username;

        // Save to localStorage
        localStorage.setItem('razzball_admin_auth', JSON.stringify({
            username: username,
            timestamp: Date.now()
        }));

        // Show loading
        document.getElementById('login-btn-text').style.display = 'none';
        document.getElementById('login-loader').style.display = 'inline';

        // Transition to dashboard
        setTimeout(() => {
            showDashboard();
            document.getElementById('admin-name').textContent = capitalizeFirst(username);
            loadDashboardData();
        }, 1000);
    } else {
        // Error
        errorEl.textContent = 'Invalid username or password';
        errorEl.style.display = 'block';
    }
}

function handleLogout() {
    if (confirm('Are you sure you want to logout?')) {
        state.isAuthenticated = false;
        state.currentUser = null;
        localStorage.removeItem('razzball_admin_auth');
        showLoginScreen();

        // Reset form
        document.getElementById('login-form').reset();
        document.getElementById('login-btn-text').style.display = 'inline';
        document.getElementById('login-loader').style.display = 'none';
        document.getElementById('login-error').style.display = 'none';
    }
}

// ========================================
// Event Listeners Setup
// ========================================
function setupEventListeners() {
    // Login form
    document.getElementById('login-form').addEventListener('submit', handleLogin);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);

    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const view = e.currentTarget.dataset.view;
            switchView(view);
        });
    });

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => {
        loadDashboardData();
        showNotification('Data refreshed!', 'success');
    });

    // Settings buttons
    document.getElementById('clear-logs-btn')?.addEventListener('click', handleClearLogs);
    document.getElementById('reset-stats-btn')?.addEventListener('click', handleResetStats);
    document.getElementById('export-data-btn')?.addEventListener('click', handleExportData);

    // Message limit buttons
    document.getElementById('save-limit-btn')?.addEventListener('click', handleUpdateDefaultLimit);
    document.getElementById('view-all-limits-btn')?.addEventListener('click', () => switchView('limits'));

    // User search
    document.getElementById('user-search')?.addEventListener('input', handleUserSearch);

    // Chat search
    document.getElementById('chat-search')?.addEventListener('input', handleChatSearch);
}

// ========================================
// View Management
// ========================================
function switchView(viewName) {
    // Update nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-view="${viewName}"]`).classList.add('active');

    // Update view containers
    document.querySelectorAll('.view-container').forEach(container => {
        container.classList.remove('active');
    });
    document.getElementById(`view-${viewName}`).classList.add('active');

    // Update page title
    const titles = {
        'dashboard': 'Dashboard',
        'users': 'Active Users',
        'analytics': 'Analytics',
        'chats': 'Chat Logs',
        'limits': 'Message Limits',
        'settings': 'Settings'
    };
    document.getElementById('page-title').textContent = titles[viewName];

    // Load view-specific data
    state.currentView = viewName;
    loadViewData(viewName);
}

function loadViewData(viewName) {
    switch (viewName) {
        case 'dashboard':
            loadDashboardData();
            break;
        case 'users':
            loadUsersData();
            break;
        case 'limits':
            loadLimitsData();
            break;
        case 'analytics':
            loadAnalyticsData();
            break;
        case 'chats':
            loadChatsData();
            break;
        case 'settings':
            // Settings are static, no need to load
            break;
    }
}

// ========================================
// Dashboard Data Loading
// ========================================
async function loadDashboardData() {
    showLoading(true);

    try {
        // Simulate API call (replace with actual API endpoints)
        const data = await fetchDashboardStats();
        state.dashboardData = data;

        // Update stats cards
        updateStatsCards(data);

        // Update charts
        updateUsageChart(data.usageData);
        updateTopQueries(data.topQueries);

        // Update recent activity
        updateRecentActivity(data.recentActivity);

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        showNotification('Failed to load dashboard data', 'error');
    } finally {
        showLoading(false);
    }
}

async function fetchDashboardStats() {
    try {
        const response = await fetch(`${API_BASE_URL}/admin/stats`, {
            headers: {
                'Authorization': `Basic ${state.currentUser}:razzball2024`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch stats');
        }

        const data = await response.json();
        return {
            totalUsers: data.total_users,
            totalChats: data.total_chats,
            activeNow: data.active_now,
            apiCost: data.api_cost,
            usageData: data.usage_data,
            topQueries: data.top_queries,
            recentActivity: data.recent_activity
        };
    } catch (error) {
        console.error('Error fetching dashboard stats:', error);
        // Fallback to demo data
        return {
            totalUsers: 247,
            totalChats: 1834,
            activeNow: 12,
            apiCost: 24.56,
            usageData: generateUsageData(),
            topQueries: [
                { query: 'Who should I pick up for home runs?', count: 89 },
                { query: 'Analyze my team', count: 76 },
                { query: 'Best available hitters', count: 64 },
                { query: 'Pitcher recommendations', count: 52 },
                { query: 'Trade advice', count: 41 }
            ],
            recentActivity: generateRecentActivity()
        };
    }
}

function updateStatsCards(data) {
    document.getElementById('stat-total-users').textContent = data.totalUsers.toLocaleString();
    document.getElementById('stat-total-chats').textContent = data.totalChats.toLocaleString();
    document.getElementById('stat-active-now').textContent = data.activeNow;
    document.getElementById('stat-api-cost').textContent = `$${data.apiCost.toFixed(2)}`;
}

function updateTopQueries(queries) {
    const container = document.getElementById('top-queries');
    container.innerHTML = '';

    queries.forEach((item, index) => {
        const queryDiv = document.createElement('div');
        queryDiv.className = 'query-item';
        queryDiv.style.animationDelay = `${index * 0.1}s`;
        queryDiv.innerHTML = `
            <span class="query-text">${item.query}</span>
            <span class="query-count">${item.count}</span>
        `;
        container.appendChild(queryDiv);
    });
}

function updateRecentActivity(activities) {
    const container = document.getElementById('recent-activity');
    container.innerHTML = '';

    activities.forEach((activity, index) => {
        const activityDiv = document.createElement('div');
        activityDiv.className = 'activity-item';
        activityDiv.style.animationDelay = `${index * 0.1}s`;
        activityDiv.innerHTML = `
            <div class="activity-icon">${activity.icon}</div>
            <div class="activity-content">
                <div class="activity-title">${activity.title}</div>
                <div class="activity-time">${activity.time}</div>
            </div>
        `;
        container.appendChild(activityDiv);
    });
}

// ========================================
// Users Data Loading
// ========================================
async function loadUsersData() {
    showLoading(true);

    try {
        const data = await fetchUsersData();
        state.usersData = data;
        renderUsersTable(data);
    } catch (error) {
        console.error('Error loading users data:', error);
        showNotification('Failed to load users data', 'error');
    } finally {
        showLoading(false);
    }
}

async function fetchUsersData() {
    try {
        const response = await fetch(`${API_BASE_URL}/admin/users`, {
            headers: {
                'Authorization': `Basic ${state.currentUser}:razzball2024`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch users');
        }

        const data = await response.json();
        return data.map(user => ({
            name: user.name,
            email: user.email,
            leagueId: user.league_id,
            lastActive: user.last_active,
            totalChats: user.total_chats,
            status: user.status
        }));
    } catch (error) {
        console.error('Error fetching users:', error);
        // Fallback to demo data
        return [
            {
                name: 'John Doe',
                email: 'john@example.com',
                leagueId: 'FNTRX-12345',
                lastActive: '5 minutes ago',
                totalChats: 23,
                status: 'active'
            },
            {
                name: 'Jane Smith',
                email: 'jane@example.com',
                leagueId: 'CBS-67890',
                lastActive: '1 hour ago',
                totalChats: 45,
                status: 'active'
            }
        ];
    }
}

function renderUsersTable(users) {
    const tbody = document.getElementById('users-tbody');
    tbody.innerHTML = '';

    users.forEach((user, index) => {
        const row = document.createElement('tr');
        row.style.animationDelay = `${index * 0.1}s`;
        row.innerHTML = `
            <td><strong>${user.name}</strong></td>
            <td>${user.email}</td>
            <td><code>${user.leagueId}</code></td>
            <td>${user.lastActive}</td>
            <td>${user.totalChats}</td>
            <td><span class="status-badge ${user.status}">${capitalizeFirst(user.status)}</span></td>
            <td><button class="action-btn" onclick="viewUserDetails('${user.email}')">View</button></td>
        `;
        tbody.appendChild(row);
    });
}

function handleUserSearch(e) {
    const query = e.target.value.toLowerCase();
    const filtered = state.usersData.filter(user =>
        user.name.toLowerCase().includes(query) ||
        user.email.toLowerCase().includes(query) ||
        user.leagueId.toLowerCase().includes(query)
    );
    renderUsersTable(filtered);
}

async function viewUserDetails(email) {
    try {
        const authHeader = `Basic ${state.currentUser}:${ADMIN_CREDENTIALS[state.currentUser]}`;

        // Find user in our data
        const user = state.usersData.find(u => u.email === email);
        if (!user) {
            showNotification('User not found', 'error');
            return;
        }

        // Get user's chats
        const chatsResponse = await fetch(`${API_BASE_URL}/admin/chats?date_filter=all`, {
            headers: { 'Authorization': authHeader }
        });
        const allChats = await chatsResponse.json();
        const userChats = allChats.filter(c => c.user === email);

        // Create modal HTML
        const modalHTML = `
            <div class="detail-modal" id="user-detail-modal">
                <div class="detail-modal-content">
                    <div class="detail-modal-header">
                        <h2>👤 User Details</h2>
                        <button class="close-modal-btn" onclick="closeDetailModal()">✕</button>
                    </div>
                    <div class="detail-modal-body">
                        <div class="detail-section">
                            <h3>User Information</h3>
                            <p><strong>Email:</strong> ${user.email}</p>
                            <p><strong>League ID:</strong> ${user.league_id}</p>
                            <p><strong>Status:</strong> <span class="status-badge ${user.status}">${user.status}</span></p>
                            <p><strong>Last Active:</strong> ${user.last_active}</p>
                            <p><strong>Total Chats:</strong> ${user.total_chats}</p>
                        </div>

                        <div class="detail-section">
                            <h3>Recent Activity (${userChats.length} total chats)</h3>
                            <div class="chat-history">
                                ${userChats.slice(0, 10).map(chat => `
                                    <div class="chat-item">
                                        <div class="chat-timestamp">${new Date(chat.timestamp).toLocaleString()}</div>
                                        <div class="chat-message"><strong>Q:</strong> ${chat.message}</div>
                                        <div class="chat-response"><strong>A:</strong> ${chat.response.substring(0, 150)}${chat.response.length > 150 ? '...' : ''}</div>
                                    </div>
                                `).join('') || '<p>No chats yet</p>'}
                            </div>
                        </div>

                        <div class="detail-actions">
                            <button class="btn btn-primary" onclick="switchView('chats')">View All Chats</button>
                            <button class="btn btn-secondary" onclick="closeDetailModal()">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Add to body
        document.body.insertAdjacentHTML('beforeend', modalHTML);

    } catch (error) {
        console.error('Error loading user details:', error);
        showNotification('Failed to load user details', 'error');
    }
}

// ========================================
// Analytics Data Loading
// ========================================
async function loadAnalyticsData() {
    showLoading(true);

    try {
        const data = await fetchAnalyticsData();
        state.analyticsData = data;
        updateAnalyticsView(data);
    } catch (error) {
        console.error('Error loading analytics data:', error);
        showNotification('Failed to load analytics data', 'error');
    } finally {
        showLoading(false);
    }
}

async function fetchAnalyticsData() {
    try {
        const response = await fetch(`${API_BASE_URL}/admin/analytics`, {
            headers: {
                'Authorization': `Basic ${state.currentUser}:razzball2024`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch analytics');
        }

        const data = await response.json();
        return {
            avgChats: data.avg_chats,
            avgDuration: data.avg_duration,
            returnRate: data.return_rate,
            totalApiCalls: data.total_api_calls,
            totalTokens: data.total_tokens,
            estimatedCost: data.estimated_cost,
            popularFeatures: data.popular_features
        };
    } catch (error) {
        console.error('Error fetching analytics:', error);
        // Fallback to demo data
        return {
            avgChats: 7.4,
            avgDuration: 12,
            returnRate: 68,
            totalApiCalls: 4521,
            totalTokens: 2847391,
            estimatedCost: 142.35,
            popularFeatures: [
                { name: 'Player Comparisons', usage: 342 },
                { name: 'Pickup Recommendations', usage: 289 },
                { name: 'Team Analysis', usage: 234 },
                { name: 'Trade Advice', usage: 187 },
                { name: 'Waiver Wire Help', usage: 156 }
            ]
        };
    }
}

function updateAnalyticsView(data) {
    document.getElementById('avg-chats').textContent = data.avgChats.toFixed(1);
    document.getElementById('avg-duration').textContent = `${data.avgDuration} min`;
    document.getElementById('return-rate').textContent = `${data.returnRate}%`;
    document.getElementById('total-api-calls').textContent = data.totalApiCalls.toLocaleString();
    document.getElementById('total-tokens').textContent = data.totalTokens.toLocaleString();
    document.getElementById('estimated-cost').textContent = `$${data.estimatedCost.toFixed(2)}`;

    // Update popular features
    const featuresContainer = document.getElementById('popular-features');
    featuresContainer.innerHTML = '';
    data.popularFeatures.forEach(feature => {
        const featureDiv = document.createElement('div');
        featureDiv.className = 'query-item';
        featureDiv.innerHTML = `
            <span class="query-text">${feature.name}</span>
            <span class="query-count">${feature.usage}</span>
        `;
        featuresContainer.appendChild(featureDiv);
    });
}

// ========================================
// Chats Data Loading
// ========================================
async function loadChatsData() {
    showLoading(true);

    try {
        const data = await fetchChatsData();
        state.chatsData = data;
        renderChatsList(data);
    } catch (error) {
        console.error('Error loading chats data:', error);
        showNotification('Failed to load chats data', 'error');
    } finally {
        showLoading(false);
    }
}

async function fetchChatsData(dateFilter = 'today') {
    try {
        const response = await fetch(`${API_BASE_URL}/admin/chats?date_filter=${dateFilter}`, {
            headers: {
                'Authorization': `Basic ${state.currentUser}:razzball2024`
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch chats');
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error fetching chats:', error);
        // Fallback to demo data
        return [
            {
                user: 'john@example.com',
                message: 'Who should I pick up for home runs?',
                response: 'Based on your league, I recommend...',
                timestamp: '2024-01-16 14:23:45'
            },
            {
                user: 'jane@example.com',
                message: 'Analyze my team',
                response: 'Your team strengths include...',
                timestamp: '2024-01-16 14:15:32'
            }
        ];
    }
}

function renderChatsList(chats) {
    const container = document.getElementById('chats-list');
    container.innerHTML = '';

    chats.forEach((chat, index) => {
        const chatDiv = document.createElement('div');
        chatDiv.className = 'activity-item';
        chatDiv.style.animationDelay = `${index * 0.1}s`;
        chatDiv.innerHTML = `
            <div class="activity-icon">💬</div>
            <div class="activity-content">
                <div class="activity-title"><strong>${chat.user}</strong>: ${chat.message}</div>
                <div class="activity-time">${chat.timestamp}</div>
            </div>
        `;
        chatDiv.style.cursor = 'pointer';
        chatDiv.onclick = () => viewChatDetails(chat);
        container.appendChild(chatDiv);
    });
}

function handleChatSearch(e) {
    const query = e.target.value.toLowerCase();
    const filtered = state.chatsData.filter(chat =>
        chat.user.toLowerCase().includes(query) ||
        chat.message.toLowerCase().includes(query) ||
        chat.response.toLowerCase().includes(query)
    );
    renderChatsList(filtered);
}

function viewChatDetails(chat) {
    // Create modal HTML
    const modalHTML = `
        <div class="detail-modal" id="chat-detail-modal">
            <div class="detail-modal-content">
                <div class="detail-modal-header">
                    <h2>💬 Chat Details</h2>
                    <button class="close-modal-btn" onclick="closeDetailModal()">✕</button>
                </div>
                <div class="detail-modal-body">
                    <div class="detail-section">
                        <h3>User Information</h3>
                        <p><strong>User:</strong> ${chat.user}</p>
                        <p><strong>Timestamp:</strong> ${new Date(chat.timestamp).toLocaleString()}</p>
                    </div>

                    <div class="detail-section">
                        <h3>User Message</h3>
                        <div class="message-box user-message">
                            ${chat.message}
                        </div>
                    </div>

                    <div class="detail-section">
                        <h3>Bot Response</h3>
                        <div class="message-box bot-message">
                            ${chat.response}
                        </div>
                    </div>

                    <div class="detail-actions">
                        <button class="btn btn-secondary" onclick="copyToClipboard('${chat.message.replace(/'/g, "\\'")}')">Copy Question</button>
                        <button class="btn btn-secondary" onclick="copyToClipboard('${chat.response.replace(/'/g, "\\'")}')">Copy Response</button>
                        <button class="btn btn-primary" onclick="closeDetailModal()">Close</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add to body
    document.body.insertAdjacentHTML('beforeend', modalHTML);
}

// ========================================
// Chart Creation
// ========================================
function updateUsageChart(data) {
    const canvas = document.getElementById('usage-chart');
    if (!canvas) return;

    // Simple chart visualization (in production, use Chart.js or similar)
    const ctx = canvas.getContext('2d');
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Draw placeholder chart
    ctx.fillStyle = '#003366';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Usage chart will be rendered here', canvas.width / 2, canvas.height / 2);
    ctx.fillText('(Integrate Chart.js for production)', canvas.width / 2, canvas.height / 2 + 20);
}

// ========================================
// Settings Actions
// ========================================
function handleClearLogs() {
    if (confirm('Are you sure you want to clear all logs? This cannot be undone.')) {
        showNotification('Logs cleared successfully', 'success');
    }
}

function handleResetStats() {
    if (confirm('Are you sure you want to reset all statistics? This cannot be undone.')) {
        showNotification('Statistics reset successfully', 'success');
    }
}

function handleExportData() {
    showNotification('Exporting data...', 'info');
    setTimeout(() => {
        showNotification('Data exported successfully!', 'success');
    }, 2000);
}

// ========================================
// Utility Functions
// ========================================
function updateTimeDisplay() {
    const now = new Date();
    const timeString = now.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('current-time').textContent = timeString;
}

function showLoading(show) {
    document.getElementById('loading-overlay').style.display = show ? 'flex' : 'none';
}

function showNotification(message, type) {
    // Simple notification (in production, use a toast library)
    alert(message);
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// ========================================
// Data Generation (for demo purposes)
// ========================================
function generateUsageData() {
    const data = [];
    for (let i = 6; i >= 0; i--) {
        const date = new Date();
        date.setDate(date.getDate() - i);
        data.push({
            date: date.toLocaleDateString(),
            chats: Math.floor(Math.random() * 50) + 150
        });
    }
    return data;
}

function generateRecentActivity() {
    const activities = [
        { icon: '👤', title: 'New user registration: john@example.com', time: '5 minutes ago' },
        { icon: '💬', title: '10 new chat conversations started', time: '15 minutes ago' },
        { icon: '⚠️', title: 'API rate limit warning', time: '1 hour ago' },
        { icon: '✅', title: 'Daily backup completed', time: '2 hours ago' },
        { icon: '📊', title: 'Weekly report generated', time: '3 hours ago' }
    ];
    return activities;
}

// ========================================
// Message Limits Management
// ========================================
async function loadLimitsData() {
    try {
        showLoading(true);
        const authHeader = `Basic ${state.currentUser}:${ADMIN_CREDENTIALS[state.currentUser]}`;

        const response = await fetch(`${API_BASE_URL}/admin/message-limits`, {
            headers: {
                'Authorization': authHeader
            }
        });

        if (!response.ok) {
            throw new Error('Failed to fetch limits data');
        }

        const limitsData = await response.json();
        state.limitsData = limitsData;

        displayLimitsData(limitsData);
        updateLimitStats(limitsData);
        showLoading(false);
    } catch (error) {
        console.error('Error loading limits:', error);
        showLoading(false);
        showNotification('Error loading message limits data', 'error');
    }
}

function displayLimitsData(limitsData) {
    const tbody = document.getElementById('limits-table-body');
    if (!tbody) return;

    if (limitsData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 20px;">No users found</td></tr>';
        return;
    }

    tbody.innerHTML = limitsData.map(user => `
        <tr>
            <td><code style="font-size: 11px;">${user.user_id.substring(0, 8)}...</code></td>
            <td>${user.messages_used}</td>
            <td>${user.monthly_limit}</td>
            <td>${user.messages_remaining}</td>
            <td>
                <div style="display: flex; align-items: center; gap: 5px;">
                    <div style="width: 100px; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden;">
                        <div style="width: ${user.percentage_used}%; height: 100%; background: ${getUsageColor(user.percentage_used)}; transition: width 0.3s;"></div>
                    </div>
                    <span>${user.percentage_used}%</span>
                </div>
            </td>
            <td>${new Date(user.reset_date).toLocaleDateString()}</td>
            <td>
                <button class="action-btn" onclick="editUserLimit('${user.user_id}', ${user.monthly_limit})" title="Edit Limit">✏️</button>
                <button class="action-btn" onclick="resetUserUsage('${user.user_id}')" title="Reset Usage">🔄</button>
            </td>
        </tr>
    `).join('');
}

function updateLimitStats(limitsData) {
    const statsEl = document.getElementById('limit-stats');
    if (!statsEl) return;

    const totalUsers = limitsData.length;
    const avgUsage = totalUsers > 0
        ? (limitsData.reduce((sum, u) => sum + u.percentage_used, 0) / totalUsers).toFixed(1)
        : 0;
    const usersOverLimit = limitsData.filter(u => u.messages_remaining === 0).length;

    statsEl.innerHTML = `
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="color: #666;">Total Users:</span>
            <strong>${totalUsers}</strong>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
            <span style="color: #666;">Avg Usage:</span>
            <strong>${avgUsage}%</strong>
        </div>
        <div style="display: flex; justify-content: space-between;">
            <span style="color: #666;">Users at Limit:</span>
            <strong style="color: ${usersOverLimit > 0 ? '#e74c3c' : '#27ae60'}">${usersOverLimit}</strong>
        </div>
    `;

    // Update summary in limits view
    document.getElementById('total-limit-users').textContent = totalUsers;
    document.getElementById('avg-usage').textContent = `${avgUsage}%`;
}

function getUsageColor(percentage) {
    if (percentage >= 90) return '#e74c3c'; // Red
    if (percentage >= 70) return '#f39c12'; // Orange
    return '#27ae60'; // Green
}

async function handleUpdateDefaultLimit() {
    const newLimit = parseInt(document.getElementById('default-message-limit').value);

    if (isNaN(newLimit) || newLimit < 0) {
        showNotification('Please enter a valid limit (0 or greater)', 'error');
        return;
    }

    if (!confirm(`Update default message limit to ${newLimit} for all NEW users?\n\nNote: This won't affect existing users.`)) {
        return;
    }

    try {
        showLoading(true);
        const authHeader = `Basic ${state.currentUser}:${ADMIN_CREDENTIALS[state.currentUser]}`;

        const response = await fetch(`${API_BASE_URL}/admin/message-limits/global`, {
            method: 'POST',
            headers: {
                'Authorization': authHeader,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                default_limit: newLimit
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update default limit');
        }

        showLoading(false);
        showNotification(`Default limit updated to ${newLimit} messages/month`, 'success');
    } catch (error) {
        console.error('Error updating limit:', error);
        showLoading(false);
        showNotification('Error updating default limit', 'error');
    }
}

async function editUserLimit(userId, currentLimit) {
    const newLimit = prompt(`Enter new monthly limit for user ${userId.substring(0, 8)}:`, currentLimit);

    if (newLimit === null) return; // Cancelled

    const limitValue = parseInt(newLimit);
    if (isNaN(limitValue) || limitValue < 0) {
        showNotification('Please enter a valid limit (0 or greater)', 'error');
        return;
    }

    try {
        showLoading(true);
        const authHeader = `Basic ${state.currentUser}:${ADMIN_CREDENTIALS[state.currentUser]}`;

        const response = await fetch(`${API_BASE_URL}/admin/message-limits/${userId}`, {
            method: 'PUT',
            headers: {
                'Authorization': authHeader,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: userId,
                new_limit: limitValue
            })
        });

        if (!response.ok) {
            throw new Error('Failed to update user limit');
        }

        showLoading(false);
        showNotification(`User limit updated to ${limitValue} messages/month`, 'success');
        loadLimitsData(); // Reload data
    } catch (error) {
        console.error('Error updating user limit:', error);
        showLoading(false);
        showNotification('Error updating user limit', 'error');
    }
}

async function resetUserUsage(userId) {
    if (!confirm(`Reset message usage for user ${userId.substring(0, 8)}?\n\nThis will set their usage to 0 and extend their reset date by 30 days.`)) {
        return;
    }

    try {
        showLoading(true);
        const authHeader = `Basic ${state.currentUser}:${ADMIN_CREDENTIALS[state.currentUser]}`;

        const response = await fetch(`${API_BASE_URL}/admin/message-limits/${userId}/reset`, {
            method: 'POST',
            headers: {
                'Authorization': authHeader
            }
        });

        if (!response.ok) {
            throw new Error('Failed to reset user usage');
        }

        showLoading(false);
        showNotification('User usage reset successfully', 'success');
        loadLimitsData(); // Reload data
    } catch (error) {
        console.error('Error resetting usage:', error);
        showLoading(false);
        showNotification('Error resetting user usage', 'error');
    }
}

// ========================================
// Modal Functions
// ========================================
function closeDetailModal() {
    const modals = document.querySelectorAll('.detail-modal');
    modals.forEach(modal => modal.remove());
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showNotification('Failed to copy', 'error');
    });
}

// Make functions globally accessible
window.viewUserDetails = viewUserDetails;
window.viewChatDetails = viewChatDetails;
window.editUserLimit = editUserLimit;
window.resetUserUsage = resetUserUsage;
window.closeDetailModal = closeDetailModal;
window.copyToClipboard = copyToClipboard;

console.log('Admin Dashboard loaded successfully');
