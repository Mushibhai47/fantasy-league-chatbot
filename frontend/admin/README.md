# Razzball Fantasy Baseball Chatbot - Admin Dashboard

## 📊 Overview

Beautiful, fully-animated admin dashboard for Rudy and Grey to monitor and manage the Razzball Fantasy Baseball Chatbot system.

## ✨ Features

### Dashboard
- **Real-time Statistics**: Total users, chats, active users, API costs
- **Usage Charts**: Visual representation of usage over time
- **Top Queries**: Most popular user questions
- **Recent Activity Feed**: Live activity monitoring

### Active Users
- **User Management**: View all users with their league data
- **Search & Filter**: Find users by name, email, or league ID
- **User Details**: Total chats, last active time, status
- **Quick Actions**: View detailed user information

### Analytics
- **Engagement Metrics**: Average chats per user, session duration, return rate
- **Popular Features**: Most used chatbot features
- **API Usage**: Total API calls, tokens used, estimated costs
- **Peak Usage Hours**: Heatmap showing when users are most active

### Chat Logs
- **Conversation History**: View all user conversations
- **Search Functionality**: Find specific chats
- **Date Filtering**: Filter by today, week, month, or all time
- **Chat Details**: View full conversation threads

### Settings
- **Admin Access**: Manage Rudy and Grey's access
- **System Configuration**: API URLs, file size limits, timeouts
- **Notifications**: Email alerts for new users, daily reports, errors
- **Danger Zone**: Clear logs, reset stats, export data

## 🎨 Design Features

### Animations
- ✅ Fade-in page transitions
- ✅ Slide-in navigation items
- ✅ Scale animations for cards
- ✅ Hover effects on all interactive elements
- ✅ Pulse animation on logo
- ✅ Loading spinners
- ✅ Smooth transitions everywhere

### Visual Elements
- ✅ Razzball brand colors (Blue #003366, Orange #FF6B35)
- ✅ Gradient backgrounds
- ✅ Card-based layout with shadows
- ✅ Icon-based navigation
- ✅ Status badges
- ✅ Responsive design

## 🔐 Authentication

**Default Login Credentials:**
- **Rudy**: Username: `rudy`, Password: `razzball2024`
- **Grey**: Username: `grey`, Password: `razzball2024`

⚠️ **Important**: Change these credentials in production! They're hardcoded in `admin.js` line 14.

## 🚀 Testing Locally

### Method 1: Standalone Testing

1. **Start the backend** (if not already running):
   ```bash
   cd c:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\backend
   START_BACKEND_CLEAN.bat
   ```

2. **Serve the admin panel**:
   ```bash
   cd c:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\frontend\admin
   python -m http.server 3004
   ```

3. **Open in browser**:
   ```
   http://localhost:3004
   ```

4. **Login** with credentials:
   - Username: `rudy` or `grey`
   - Password: `razzball2024`

### Method 2: Integration Testing

Once both backend and admin panel are running, test the integration:
1. Login to admin panel
2. Navigate through all views
3. Test search functionality
4. Verify data loading

## 📂 Files Structure

```
frontend/admin/
├── index.html          # Main admin dashboard HTML
├── admin.css           # Complete styling with animations
├── admin.js            # All functionality and API integration
└── README.md           # This file
```

## 🔧 Configuration

### Update API URL for Production

Edit `admin.js` line 8:

```javascript
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : 'https://chatbot.razzball.com/api';  // Update this URL
```

### Change Admin Credentials

Edit `admin.js` lines 14-17:

```javascript
const ADMIN_CREDENTIALS = {
    'rudy': 'YOUR_SECURE_PASSWORD_HERE',
    'grey': 'YOUR_SECURE_PASSWORD_HERE'
};
```

## 🌐 Deployment

### Option 1: Deploy with Frontend

Upload `frontend/admin/*` files to your server alongside the embed widget:

```
chatbot.razzball.com/
├── embed/
│   ├── index.html
│   ├── embed.css
│   └── embed.js
└── admin/
    ├── index.html
    ├── admin.css
    └── admin.js
```

Access at: `https://chatbot.razzball.com/admin`

### Option 2: Separate Subdomain

Deploy admin panel to a separate subdomain for added security:

```
admin.chatbot.razzball.com/
├── index.html
├── admin.css
└── admin.js
```

### Option 3: Password-Protected Directory

1. Upload files to server
2. Add `.htaccess` password protection
3. Create `.htpasswd` file with encrypted passwords

## 🔒 Security Recommendations

### For Production:

1. **Move Authentication to Backend**
   - Don't hardcode credentials in JavaScript
   - Create backend `/admin/login` endpoint
   - Use JWT tokens for session management
   - Implement rate limiting

2. **Add HTTPS**
   - Require HTTPS for all admin pages
   - SSL certificate required

3. **Add IP Whitelist** (Optional)
   - Only allow access from Rudy/Grey's IP addresses
   - Configure in server (nginx/Apache)

4. **Add Session Timeout**
   - Auto-logout after 30 minutes of inactivity
   - Already configured in localStorage check

5. **Add Activity Logging**
   - Log all admin actions
   - Track who made what changes

## 📊 Backend Integration

### Required Backend Endpoints

The admin panel expects these API endpoints (create in backend):

```python
# Dashboard Stats
GET /admin/stats
Response: {
    "total_users": 247,
    "total_chats": 1834,
    "active_now": 12,
    "api_cost": 24.56,
    "usage_data": [...],
    "top_queries": [...],
    "recent_activity": [...]
}

# Users List
GET /admin/users
Response: [
    {
        "name": "John Doe",
        "email": "john@example.com",
        "league_id": "FNTRX-12345",
        "last_active": "2024-01-16T14:23:45Z",
        "total_chats": 23,
        "status": "active"
    },
    ...
]

# Analytics Data
GET /admin/analytics
Response: {
    "avg_chats": 7.4,
    "avg_duration": 12,
    "return_rate": 68,
    "total_api_calls": 4521,
    "total_tokens": 2847391,
    "estimated_cost": 142.35,
    "popular_features": [...]
}

# Chat Logs
GET /admin/chats?date_filter=today
Response: [
    {
        "user": "john@example.com",
        "message": "Who should I pick up?",
        "response": "Based on your league...",
        "timestamp": "2024-01-16T14:23:45Z"
    },
    ...
]

# Admin Actions
POST /admin/clear-logs
POST /admin/reset-stats
POST /admin/export-data
```

## 🎯 Current Status

### ✅ Complete
- Beautiful UI with animations
- Login/authentication system
- Dashboard layout
- Navigation system
- All view containers
- Mock data display
- Search functionality
- Settings page

### 🔄 Needs Backend Integration
- Connect to real API endpoints
- Implement actual data fetching
- Add Chart.js for charts
- Add real-time WebSocket updates
- Implement export functionality

## 🚧 Next Steps

1. **Create Backend Endpoints**
   - Add admin routes to FastAPI backend
   - Implement data aggregation
   - Add authentication endpoints

2. **Add Chart Library**
   - Install Chart.js
   - Create real usage charts
   - Add peak hours heatmap

3. **Add Real-time Updates**
   - WebSocket connection for live stats
   - Auto-refresh dashboard every 30 seconds

4. **Add Export Functionality**
   - CSV export for users
   - JSON export for chats
   - PDF reports

5. **Add Notifications**
   - Email alerts for admins
   - In-app toast notifications

## 💡 Usage Tips

### For Rudy & Grey:

1. **Check Dashboard Daily**
   - Monitor active users
   - Track API costs
   - Review popular queries

2. **Use Search Effectively**
   - Find specific users quickly
   - Search chat logs for issues

3. **Export Data Regularly**
   - Backup user data
   - Generate monthly reports

4. **Monitor API Costs**
   - Watch the daily cost stat
   - Check analytics for token usage

## 🐛 Troubleshooting

### Can't Login
- Check username/password (case-sensitive)
- Clear localStorage: `localStorage.clear()`
- Try different browser

### Data Not Loading
- Check backend is running
- Verify API_BASE_URL in admin.js
- Check browser console for errors

### Animations Not Working
- Clear browser cache
- Ensure CSS file loaded
- Try hard refresh (Ctrl+F5)

## 📞 Support

For issues or questions:
1. Check browser console for errors
2. Verify backend is running
3. Check API endpoint responses
4. Review this README

## 🎨 Customization

### Change Colors

Edit `admin.css` lines 9-30 (CSS variables):

```css
:root {
    --primary-color: #003366;      /* Deep Blue */
    --secondary-color: #FF6B35;    /* Action Orange */
    --accent-color: #2E7D32;       /* Success Green */
    /* ... */
}
```

### Add New Views

1. Add nav item in `index.html`
2. Add view container
3. Update `switchView()` in `admin.js`
4. Create load function

### Modify Stats Cards

Edit `index.html` lines 75-115 to change stats displayed.

## 📈 Future Enhancements

- [ ] Real-time WebSocket updates
- [ ] Advanced filtering options
- [ ] User ban/unban functionality
- [ ] System health monitoring
- [ ] Email notification system
- [ ] Multi-language support
- [ ] Mobile app version
- [ ] Advanced analytics charts
- [ ] A/B testing dashboard
- [ ] API rate limiting controls

---

**Built with ❤️ for Razzball Fantasy Baseball**
