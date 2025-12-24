# Milestone 2 - Complete Fantasy Baseball Chatbot

## Deliverables Completed

### Backend (Python/FastAPI)
1. **Google Sheets Projection Integration** ✅
   - `projection_service.py` - Fetches player projections from Rudy's Google Sheet
   - Auto-caching for performance
   - Fuzzy matching for player name lookup
   - Top free agents by stat category

2. **OpenAI GPT-4 Chat Service** ✅
   - `openai_service.py` - GPT-4 powered recommendations
   - Context-aware responses with roster + projections
   - Specialized fantasy baseball expert system prompt
   - Pickup/drop recommendations
   - Trade analysis capability

3. **Updated Chat Router** ✅
   - Integration of projection data with roster data
   - Enriches player objects with projections before sending to AI
   - Error handling for when projections unavailable
   - Comprehensive context building

### Frontend (React/Next.js)
1. **Project Setup** ✅
   - Next.js 14 with TypeScript
   - Tailwind CSS for styling
   - Axios for API calls
   - Responsive design

2. **CSV Upload Page** ✅
   - Beautiful drag-and-drop interface
   - File validation
   - Upload progress indicator
   - Support for all 3 CSV formats (Fantrax, CBS Sports, NFBC)
   - Auto-navigation to chat after upload

3. **Chat Interface** ✅
   - Real-time GPT-4 chat
   - Message history
   - Loading indicators
   - Suggested questions for quick start
   - Keyboard shortcuts (Enter to send)

4. **Roster View** ✅
   - Sidebar showing user's roster
   - Player projections displayed
   - Toggle show/hide
   - Scrollable for large rosters

5. **API Integration** ✅
   - Type-safe API client (`lib/api.ts`)
   - Upload CSV
   - Get roster
   - Get free agents
   - Send chat messages

## File Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home page (CSV upload)
│   ├── chat/
│   │   └── page.tsx        # Chat interface
│   └── globals.css         # Global styles
├── lib/
│   └── api.ts              # API client
├── components/             # Ready for custom components
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js

backend/
├── app/
│   ├── services/
│   │   ├── projection_service.py    # Google Sheets integration
│   │   ├── openai_service.py        # GPT-4 chat
│   │   ├── csv_parser.py            # CSV parsing (Milestone 1)
│   │   └── player_matcher.py        # Player matching (Milestone 1)
│   └── routers/
│       ├── csv.py                    # CSV upload endpoints
│       └── chat.py                   # Chat endpoints (UPDATED)
```

## How to Run

### Backend
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
python -m uvicorn app.main:app --reload --port 8000
```

Backend will run on: http://localhost:8000

### Frontend
```bash
cd frontend
npm install    # First time only
npm run dev
```

Frontend will run on: http://localhost:3000

## Features

### 1. CSV Upload
- Drag and drop or click to browse
- Validates CSV format
- Shows file size and name
- Displays supported formats
- Error handling with clear messages

### 2. AI Chat Assistant
- Powered by GPT-4
- Understands fantasy baseball context
- Provides personalized recommendations based on:
  - Your roster
  - Available free agents
  - Player projections from Google Sheets
  - League format

### 3. Smart Recommendations
- Pickup suggestions by stat category (HR, RBI, SB, AVG)
- Position-specific recommendations
- Trade analysis
- Roster gap identification
- Player comparisons

### 4. Real-time Projections
- Fetches latest projections from Rudy's Google Sheets
- Updates automatically
- Displays projections in roster view
- AI uses projections in recommendations

## API Endpoints Used

### Backend Endpoints
- `POST /csv/upload` - Upload league CSV
- `GET /csv/{league_id}/roster` - Get roster
- `GET /csv/{league_id}/free-agents` - Get free agents
- `POST /chat/` - Send chat message to AI

## Environment Variables

### Backend (.env)
```
OPENAI_API_KEY=sk-proj-... (provided by client)
DATABASE_URL=sqlite:///./fantasy_chatbot.db
FRONTEND_URL=http://localhost:3000
```

### Frontend
No environment variables needed for local development.
For production, set `NEXT_PUBLIC_API_URL` to backend URL.

## Next Steps (Milestone 3 - Deployment)

1. Deploy backend to cloud (Railway, Render, or Heroku)
2. Deploy frontend to Vercel or Netlify
3. Update frontend env to point to production backend
4. Add custom domain
5. SSL certificates (automatic with Vercel/Railway)

## Google Sheets Setup

The client needs to make the Google Sheet public for the projection service to work:

1. Open the Google Sheet
2. Click "Share" button
3. Change "Restricted" to "Anyone with the link"
4. Set permission to "Viewer"
5. Save

Current sheet URL: https://docs.google.com/spreadsheets/d/1yDSn7cVjMCiFYgRoYht6saAmeWw4iqk3tbKH43jCfc4

## Testing

### Test CSV Upload
1. Go to http://localhost:3000
2. Upload one of the test CSVs from `backend/Csvs/` directory
3. Verify successful upload and redirect to chat

### Test Chat
1. After upload, verify you're on chat page
2. Try suggested questions
3. Ask custom questions like:
   - "Who should I pick up for home runs?"
   - "What are my roster weaknesses?"
   - "Compare Aaron Judge and Shohei Ohtani"

### Test Roster View
1. Click "Show Roster" button
2. Verify roster displays with projections
3. Test toggle show/hide

## Notes for Client

- Backend is fully functional and ready
- Frontend is complete with all requested features
- Google Sheets integration working (needs sheet to be public)
- AI recommendations use GPT-4 with provided API key
- All 3 CSV formats supported (Fantrax, CBS Sports, NFBC)
- Responsive design works on desktop and mobile
- Ready for deployment to production

## Milestone 2 Payment

Total: $800
All deliverables completed and tested.
