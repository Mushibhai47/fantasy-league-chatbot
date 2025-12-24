# Testing Guide - Fantasy League Chatbot

**Before Showing to Rudy**

---

## 🎯 Pre-Test Setup

### **1. Set Up Environment**

```bash
cd C:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot\backend

# Create virtual environment
python -m venv venv

# Activate
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt
```

### **2. Set Up PostgreSQL Database**

**Option A: Railway (Recommended)**
1. Go to https://railway.app/
2. Sign up / Log in
3. Click "New Project" → "Provision PostgreSQL"
4. Copy the DATABASE_URL from "Connect" tab

**Option B: Local PostgreSQL**
```bash
createdb fantasy_chatbot
# DATABASE_URL=postgresql://localhost/fantasy_chatbot
```

### **3. Configure .env File**

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=postgresql://your-url-here
RAZZBALL_API_KEY=71yqx5zf-be81-2a2c-860p-oxch3odcgszm
RAZZBALL_API_BASE_URL=https://api.razzball.com/mlb
PLAYER_REFERENCE_URL=https://razzball.com/mlbamidsshhh/
SECRET_KEY=your-random-secret-key-change-this
FRONTEND_URL=http://localhost:3000
ENVIRONMENT=development
```

---

## 🧪 Running Tests

### **Test 1: Razzball API**

```bash
cd backend
python test_razzball_api.py
```

**Expected Output:**
```
🔍 Testing Razzball API...
📅 Date: 2025-10-28
🔗 URL: https://api.razzball.com/mlb/projections/daily/2025-10-28

📊 Status Code: 200
✅ SUCCESS! Received data

📈 Data structure:
  - Type: <class 'list'>
  - Number of players: 500+

🎯 Sample player (first entry):
{
  "name": "Aaron Judge",
  "team": "NYY",
  "hr": 0.29,
  ...
}
```

**If it fails:** API might not have data for that date. Try different dates.

---

### **Test 2: Full System Test**

```bash
cd backend
python test_full_system.py
```

**Expected Output:**
```
🧪 FANTASY LEAGUE CHATBOT - FULL SYSTEM TEST

🗑️  Resetting database...
✅ Database reset complete

============================================================
TEST 1: CSV PARSING
============================================================

✅ Fantrax:
   - Type: fantrax
   - Total players: 1200+
   - Owned: 300+
   - Free Agents: 900+
   - Sample: Garrett Crochet

✅ CBS Sports:
   - Type: cbs
   - Total players: 800+
   - Owned: 250+
   - Free Agents: 550+
   - Sample: Shohei Ohtani

✅ NFBC:
   - Type: nfbc
   - Total players: 900+
   - Owned: 280+
   - Free Agents: 620+
   - Sample: Abbott, Andrew

============================================================
TEST 2: PROJECTION LOADING
============================================================

✅ Loaded 500 hitter projections
   - Sample: Aaron Judge - 0.29 HR

📊 Database Stats:
   - Players in DB: 500
   - Projections in DB: 500

============================================================
TEST 3: PLAYER MATCHING
============================================================

✅ Matched: Aaron Judge → Aaron Judge (ID: 1)
✅ Matched: Shohei Ohtani → Shohei Ohtani (ID: 2)
✅ Matched: Juan Soto → Juan Soto (ID: 3)

📊 Match Rate: 3/3

============================================================
TEST 4: FULL WORKFLOW (Fantrax)
============================================================

Step 1: Parsing CSV...
   ✅ Parsed 1200 players

Step 2: Creating league record...
   ✅ League created: <uuid>

Step 3: Matching and storing players...
   ✅ Stored 50 roster entries

Step 4: Querying rosters...
   ✅ Total rosters: 50
   ✅ Free agents: 35

Step 5: Sample roster with projections:
   - Garrett Crochet (AA): 0.15 HR, 0.45 RBI
   - Juan Soto (MG): 0.43 HR, 1.05 RBI
   - Aroldis Chapman (Doc): 0.02 HR, 0.12 RBI
   - Edwin Diaz (AA): 0.01 HR, 0.08 RBI
   - Kyle Tucker (Free Agent): 0.25 HR, 0.68 RBI

✅ FULL WORKFLOW SUCCESS!

============================================================
TEST SUMMARY
============================================================

✅ PASS - Csv Parsing
✅ PASS - Projections
✅ PASS - Player Matching
✅ PASS - Full Workflow

============================================================
🎉 ALL TESTS PASSED!
============================================================
```

**If any test fails:** Check error messages and fix before proceeding.

---

### **Test 3: Start FastAPI Server**

```bash
cd backend
uvicorn app.main:app --reload
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

**Test the server:**
```bash
# Open browser: http://localhost:8000
# Should see: {"message": "Fantasy League Chatbot API", ...}

# Check API docs: http://localhost:8000/docs
# Should see interactive Swagger UI
```

---

## 🔥 Manual API Testing

### **Test 4: Upload CSV via API**

**Using cURL (Windows PowerShell):**

```powershell
curl -X POST "http://localhost:8000/api/csv/upload" `
  -F "file=@C:\Users\DELL\Downloads\Rudy\Csvs\Fantrax League Player File.csv"
```

**Expected Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "league_type": "fantrax",
  "total_players": 1200,
  "owned_players": 300,
  "free_agents": 900,
  "uploaded_at": "2025-11-30T22:00:00"
}
```

**Save the `id` - you'll need it for the next test!**

---

### **Test 5: Get Roster**

Replace `<league_id>` with the ID from Test 4:

```powershell
curl "http://localhost:8000/api/csv/<league_id>/roster"
```

**Expected Response:**
```json
{
  "league_id": "550e8400-e29b-41d4-a716-446655440000",
  "league_type": "fantrax",
  "players": [
    {
      "id": 1,
      "name": "Garrett Crochet",
      "mlb_team": "BOS",
      "position": "SP",
      "owner": "AA",
      "hr": 0.01,
      "rbi": 0.15,
      "sb": 0.00,
      "avg": 0.245
    },
    ...
  ]
}
```

---

### **Test 6: Get Free Agents**

```powershell
curl "http://localhost:8000/api/csv/<league_id>/free-agents"
```

**Expected Response:**
```json
{
  "league_id": "550e8400-e29b-41d4-a716-446655440000",
  "league_type": "fantrax",
  "players": [
    {
      "id": 50,
      "name": "Kyle Tucker",
      "mlb_team": "HOU",
      "position": "OF",
      "owner": "Free Agent",
      "hr": 0.25,
      "rbi": 0.68,
      "sb": 0.12,
      "avg": 0.289
    },
    ...
  ]
}
```

---

### **Test 7: Chat with AI**

**You need an OpenAI API key for this test.**

```powershell
curl -X POST "http://localhost:8000/api/chat/" `
  -H "Content-Type: application/json" `
  -d '{
    "league_id": "<league_id>",
    "message": "Who are the top 5 free agents for power?",
    "user_api_key": "sk-your-openai-key-here",
    "provider": "openai"
  }'
```

**Expected Response:**
```json
{
  "message": "Who are the top 5 free agents for power?",
  "response": "Based on the projections, here are the top 5 free agents for power:\n\n1. Kyle Tucker (HOU, OF) - 0.25 HR per game\n2. Jorge Soler (SFG, OF) - 0.23 HR per game\n3. Kyle Schwarber (PHI, OF) - 0.28 HR per game\n...",
  "tokens_used": 450
}
```

---

## ✅ Pre-Demo Checklist

Before showing to Rudy, verify ALL these work:

- [ ] Database is set up and connected
- [ ] `test_razzball_api.py` passes
- [ ] `test_full_system.py` all tests pass
- [ ] FastAPI server starts without errors
- [ ] Can upload Fantrax CSV
- [ ] Can upload CBS Sports CSV
- [ ] Can upload NFBC CSV
- [ ] Can retrieve roster for a league
- [ ] Can retrieve free agents
- [ ] Chat endpoint works (with OpenAI key)
- [ ] All player matching is accurate
- [ ] Projections are loaded correctly

---

## 🐛 Common Issues & Fixes

### **Issue: Database Connection Error**
```
sqlalchemy.exc.OperationalError: could not connect to server
```
**Fix:** Check DATABASE_URL in `.env` is correct

---

### **Issue: ModuleNotFoundError**
```
ModuleNotFoundError: No module named 'fastapi'
```
**Fix:** Activate venv and install requirements:
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

---

### **Issue: CSV File Not Found**
```
FileNotFoundError: [Errno 2] No such file or directory
```
**Fix:** Check CSV paths in test scripts are correct relative to where you run them

---

### **Issue: Player Matching Low Accuracy**
**Fix:**
- Make sure projections are loaded first (`test_full_system.py` Test 2)
- Check player names match between CSV and projections

---

## 📊 Expected Performance

- **CSV Upload:** < 5 seconds for 1000 players
- **Player Matching:** 95%+ accuracy
- **Chat Response:** 2-5 seconds
- **Database Queries:** < 1 second

---

## 🎥 Demo Preparation

### **What to Show Rudy:**

1. **Upload CSV:**
   - Show Swagger UI (http://localhost:8000/docs)
   - Upload Fantrax CSV
   - Show successful response

2. **View Roster:**
   - Show parsed players
   - Show team owners
   - Show free agents

3. **Projections:**
   - Show players have projection data
   - Explain daily/weekly/ROS structure

4. **Chat Demo:**
   - Ask: "Who should I pick up for power?"
   - Ask: "What's my weakest position?"
   - Ask: "Should I pick up Kyle Tucker?"
   - Show intelligent responses

5. **Multi-League Support:**
   - Upload CBS Sports CSV
   - Upload NFBC CSV
   - Show all 3 work

---

## 📝 Test Results Log

Fill this out before demo:

**Date Tested:** _______________
**Tester:** Musharaf Shah

| Test | Status | Notes |
|------|--------|-------|
| API Connection | ✅ / ❌ | |
| CSV Parsing (Fantrax) | ✅ / ❌ | |
| CSV Parsing (CBS) | ✅ / ❌ | |
| CSV Parsing (NFBC) | ✅ / ❌ | |
| Projections Load | ✅ / ❌ | |
| Player Matching | ✅ / ❌ | |
| Upload Endpoint | ✅ / ❌ | |
| Roster Endpoint | ✅ / ❌ | |
| Chat Endpoint | ✅ / ❌ | |

**Overall Status:** READY / NOT READY

**Notes:**
_______________________________________________________
_______________________________________________________
_______________________________________________________

---

**When all tests pass, you're ready to demo to Rudy! 🎉**
