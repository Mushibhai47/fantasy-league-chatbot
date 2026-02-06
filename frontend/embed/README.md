# Razzball Fantasy Baseball Chatbot - Embeddable Widget

## 📦 What's Included

This directory contains the embeddable chatbot widget that can be integrated into WordPress pages:

- `index.html` - Main embed page
- `embed.css` - Styled with Razzball branding (blue/orange colors)
- `embed.js` - All functionality (API key management, file upload, chat)
- `wordpress-integration.php` - WordPress shortcode integration
- `README.md` - This file

## 🎯 Features

### User Features:
- ✅ Enter and save OpenAI API key (stored locally in browser)
- ✅ Upload CSV files (Fantrax, CBS, NFBC)
- ✅ Chat with AI about fantasy baseball team
- ✅ Quick action buttons for common queries
- ✅ Settings panel to manage API key and data
- ✅ Responsive design (works on mobile)
- ✅ Razzball-themed colors and branding

### Technical Features:
- ✅ Works as standalone page OR embedded iframe
- ✅ Communicates with parent window (WordPress integration)
- ✅ Local storage for API key persistence
- ✅ Drag-and-drop file upload
- ✅ Markdown table rendering in chat
- ✅ Conversation history for context

## 🚀 Testing Locally

### Option 1: Test as Standalone Page

1. Start the backend (if not already running):
   ```bash
   cd c:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\backend
   python -m uvicorn app.main:app --reload --port 8000
   ```

2. Serve the embed folder with a simple HTTP server:
   ```bash
   cd c:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\frontend\embed
   python -m http.server 3003
   ```

3. Open in browser:
   ```
   http://localhost:3003
   ```

4. Test the flow:
   - Enter your OpenAI API key (starts with sk-...)
   - Upload a CSV file
   - Start chatting!

### Option 2: Test as Iframe Embed

1. Create a test HTML file:
   ```html
   <!DOCTYPE html>
   <html>
   <head>
       <title>Test Embed</title>
   </head>
   <body>
       <h1>Testing Razzball Chatbot Embed</h1>

       <iframe
           src="http://localhost:3003"
           width="100%"
           height="600px"
           frameborder="0"
           style="border: 1px solid #ccc;"
       ></iframe>
   </body>
   </html>
   ```

2. Open this file in your browser to test the iframe embed

## 🌐 Deploying to Production

### Step 1: Deploy Backend to chatbot.razzball.com

You'll need to deploy the FastAPI backend first. Options:

**Option A: Deploy to Railway** (Recommended - Easiest)
```bash
# Install Railway CLI
npm install -g railway

# Login
railway login

# Initialize project
cd backend
railway init

# Deploy
railway up
```

**Option B: Deploy to VPS**
- SSH into chatbot.razzball.com server
- Install Python 3.9+, pip, requirements
- Run with gunicorn/uvicorn
- Set up nginx reverse proxy

### Step 2: Deploy Frontend to chatbot.razzball.com

**Option A: Direct Hosting**
1. Upload `frontend/embed/*` files to your server
2. Point chatbot.razzball.com to serve these files
3. Update `API_BASE_URL` in embed.js to production URL

**Option B: Vercel** (If preferred)
```bash
cd frontend/embed
vercel --prod
```

### Step 3: Configure DNS & SSL

1. Ensure chatbot.razzball.com has SSL certificate (HTTPS)
2. Configure CORS on backend to allow chatbot.razzball.com
3. Test the embed loads properly

### Step 4: WordPress Integration

Add this to your theme's `functions.php`:

```php
function razzball_chatbot_shortcode() {
    return '<iframe
        src="https://chatbot.razzball.com/embed"
        width="100%"
        height="600px"
        frameborder="0"
        style="border: 1px solid #e1e8ed; border-radius: 8px;"
    ></iframe>';
}
add_shortcode('razzball_chatbot', 'razzball_chatbot_shortcode');
```

Or use the full integration from `wordpress-integration.php`

### Step 5: Test on WordPress

1. Create a new page in WordPress
2. Add the shortcode: `[razzball_chatbot]`
3. Make sure the page requires Paid Memberships Pro
4. Test the full flow

## 📝 Configuration

### Update API URL for Production

Edit `embed.js` line 8:

```javascript
const API_BASE_URL = window.location.hostname === 'localhost'
    ? 'http://localhost:8000'
    : 'https://chatbot.razzball.com/api';  // Update this URL
```

### Customize Branding

All colors are in `embed.css` at the top (CSS variables):

```css
:root {
    --primary-color: #003366;      /* Deep Blue */
    --secondary-color: #FF6B35;    /* Action Orange */
    --accent-color: #2E7D32;       /* Success Green */
    /* ... */
}
```

## 🔒 Security Notes

1. **API Keys are stored in user's browser** (localStorage)
   - Never sent to your server
   - Each user brings their own OpenAI key
   - Keys are not shared between users

2. **CORS Configuration Required**
   - Backend must allow requests from chatbot.razzball.com
   - Update FastAPI CORS settings

3. **HTTPS Required**
   - iframe embedding requires HTTPS on both sides
   - Get SSL certificate for chatbot.razzball.com

## 📊 WordPress Shortcode Options

### Basic Embed:
```
[razzball_chatbot]
```

### Advanced (with user email):
```
[razzball_chatbot_advanced]
```

### Premium Only (requires membership):
```
[razzball_chatbot_premium]
```

### Custom Dimensions:
```
[razzball_chatbot_advanced height="800px" width="100%"]
```

## 🐛 Troubleshooting

### Chatbot won't load
- Check browser console for errors
- Verify API_BASE_URL is correct
- Ensure backend is running

### File upload fails
- Check file is CSV format
- Verify backend /upload endpoint works
- Check file size (should be < 10MB)

### Chat doesn't work
- Verify OpenAI API key is valid
- Check API key starts with "sk-"
- Ensure backend can reach OpenAI API

### Iframe blocked in WordPress
- Check if page is HTTPS
- Verify iframe src is HTTPS
- Check browser console for CSP errors

## 📞 Support

If you encounter issues:
1. Check browser console for errors
2. Check backend logs
3. Verify all URLs are HTTPS
4. Test standalone embed first (http://localhost:3003)

## 🎨 Customization

Want to change the design?
- Edit `embed.css` for styling
- Modify `index.html` for layout
- Update `embed.js` for functionality

All code is commented and easy to modify!

## 📦 What's Next?

After this is working:
- [ ] Build admin panel for Rudy & Grey
- [ ] Add analytics tracking
- [ ] Create usage reports
- [ ] Add more quick action buttons
- [ ] Implement conversation history
