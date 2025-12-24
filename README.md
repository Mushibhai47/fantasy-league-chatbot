# Fantasy League Chatbot

AI-powered fantasy baseball roster assistant that combines league data with proprietary projections to provide personalized advice.

**Client:** Rudy (Razzball.com)
**Developer:** Musharaf Shah
**Start Date:** November 30, 2025
**Target Launch:** February 10, 2026
**Milestone 1:** December 29, 2025

---

## 🎯 Project Overview

This chatbot helps fantasy baseball players make informed roster decisions by:
1. Uploading their league roster (CSV from Fantrax, CBS Sports, or NFBC)
2. Combining it with Rudy's proprietary player projections
3. Answering questions like "Who should I pick up?" or "What's my weakest position?"

---

## 🏗️ Architecture

### **Backend (Python FastAPI)**
- CSV parsing for 3 league platforms
- Player matching (ID-based + fuzzy name matching)
- Projection data integration (daily, weekly, rest-of-season)
- AI chatbot (OpenAI GPT-4 / Anthropic Claude)
- PostgreSQL database

### **Frontend (Next.js 14)**
- CSV upload interface
- Chat interface
- Roster display
- Admin dashboard (later)

---

## 📁 Project Structure

```
fantasy-league-chatbot/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings
│   │   ├── database.py          # DB connection
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── league.py
│   │   │   ├── player.py
│   │   │   ├── roster.py
│   │   │   ├── projection.py
│   │   │   └── api_key.py
│   │   ├── schemas/             # Pydantic schemas
│   │   ├── routers/             # API endpoints
│   │   ├── services/            # Business logic
│   │   └── utils/               # Helper functions
│   ├── requirements.txt
│   ├── .env.example
│   └── test_razzball_api.py    # API test script
├── frontend/                    # Next.js app (to be created)
├── database/migrations/         # SQL migrations
└── README.md
```

---

## 🚀 Getting Started

### **Backend Setup**

1. **Create virtual environment:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your database credentials
```

4. **Set up PostgreSQL:**
```bash
# Local development
createdb fantasy_chatbot

# Or use Railway/Supabase for hosted PostgreSQL
```

5. **Run the server:**
```bash
uvicorn app.main:app --reload
```

6. **Test Razzball API:**
```bash
python test_razzball_api.py
```

API will be available at: `http://localhost:8000`
Docs: `http://localhost:8000/docs`

---

## 🗄️ Database Schema

### **Tables:**
- `users` - User sessions
- `leagues` - Uploaded league CSVs
- `players` - Master player reference (Razzball IDs)
- `rosters` - Players in leagues (team owners, free agents)
- `projections_daily` - Daily projections
- `projections_weekly` - Weekly projections
- `projections_ros` - Rest-of-season projections
- `api_keys` - User's OpenAI/Claude keys (encrypted)

---

## 📊 Supported League Platforms

### **1. Fantrax**
- Has unique player IDs (`*05ajh*`)
- CSV includes: Player, Team, Position, Owner
- Matching: ID-based

### **2. CBS Sports**
- NO player IDs
- CSV includes: Player (with team), Stats, Owner
- Matching: Fuzzy name matching

### **3. NFBC**
- Has numeric player IDs (11802)
- CSV includes: Player, Owner, Position, Team
- Matching: ID-based

---

## 🔌 Razzball API

**Base URL:** `https://api.razzball.com/mlb/projections/daily/<date>`

**Example:** `https://api.razzball.com/mlb/projections/daily/2025-10-28`

**Headers:**
```
Razzball-Api-Key: 71yqx5zf-be81-2a2c-860p-oxch3odcgszm
Accept: application/vnd.razzball-v1+json
```

**Response:** JSON array of player projections with stats (HR, RBI, SB, AVG, etc.)

---

## 📅 Development Timeline

### **Week 1 (Nov 30 - Dec 6)** ✅
- [x] Project structure setup
- [x] Database models
- [x] API testing script
- [ ] CSV parsers (Fantrax, CBS, NFBC)
- [ ] Player matching engine

### **Week 2-3 (Dec 7-20)**
- [ ] Projection integration
- [ ] Frontend basic UI
- [ ] CSV upload workflow

### **Week 4-5 (Dec 21 - Jan 3)**
- [ ] AI chatbot integration
- [ ] Context building
- [ ] Query handling

### **Week 6 (Jan 4-10)**
- [ ] Testing & bug fixes
- [ ] Deployment
- [ ] **MILESTONE 1 DEMO** (Dec 29)

---

## 🎯 Milestone 1 Deliverables

**Target Date:** December 29, 2025
**Payment:** $600 (30%)

**Must Have:**
1. ✅ CSV upload for all 3 leagues
2. ✅ Player matching 95%+ accurate
3. ✅ Daily projections integrated
4. ✅ Basic chatbot answering questions
5. ✅ Deployed to production

**Test Questions:**
- "Who are the top 5 free agents for home runs?"
- "What's my weakest position?"
- "Should I pick up Aaron Judge?"

---

## 🧪 Testing

**Test Razzball API:**
```bash
python test_razzball_api.py
```

**Run FastAPI server:**
```bash
uvicorn app.main:app --reload
```

**Check health:**
```bash
curl http://localhost:8000/health
```

---

## 🔐 Security

- User API keys encrypted in database
- CORS configured for frontend
- SQL injection prevention (SQLAlchemy ORM)
- Environment variables for secrets

---

## 📝 Next Steps

1. **Today (Nov 30):**
   - [x] Project structure ✅
   - [ ] Test Razzball API
   - [ ] CSV parsers

2. **Tomorrow (Dec 1):**
   - [ ] Player matching
   - [ ] Database seeding
   - [ ] Frontend init

3. **This Week:**
   - [ ] Full CSV workflow
   - [ ] Projection fetching
   - [ ] Basic UI

---

## 🤝 Contributors

**Developer:** Musharaf Shah
**Client:** Rudy (Razzball.com)
**Project Start:** November 30, 2025
**Estimated Completion:** February 10, 2026

---

## 📞 Contact

**Questions?** Contact Musharaf Shah

**Razzball API Issues?** Contact Rudy

---

**Status:** 🟢 IN PROGRESS
**Last Updated:** November 30, 2025
