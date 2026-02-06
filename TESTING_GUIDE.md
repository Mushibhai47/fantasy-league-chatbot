# 🧪 Testing Guide - What You Should See

## Port 3003 - Embed Widget (For Regular Users) ✅

**URL**: http://localhost:3003

### What You'll See:
1. **Step 1: Enter API Key**
   - A nice blue/orange interface
   - Text box asking for OpenAI API key
   - "Next" button

2. **Step 2: Upload CSV**
   - Drag-and-drop area
   - Or click to browse for your CSV file

3. **Step 3: Chat!**
   - Chat interface
   - Quick action buttons
   - Settings icon

### This is CORRECT! ✅
This is what your users will see when you embed it on WordPress.

---

## Port 3004 - Admin Dashboard (For You & Grey)

**URL**: http://localhost:3004

### If You See LOGIN SCREEN: ✅ CORRECT
- Baseball emoji logo
- "Razzball Admin" heading
- Username: `rudy` or `grey`
- Password: `razzball2024`

### If You See DASHBOARD: Already logged in!
To see login screen again:
1. Press F12 (open console)
2. Type: `localStorage.clear()`
3. Press Enter
4. Refresh page (F5)

---

## 🚨 Quick Fix

**If admin (3004) isn't working:**

Open browser console (F12) and run:
```javascript
localStorage.clear()
```

Then refresh!

---

**Both interfaces have amazing animations!** ✨