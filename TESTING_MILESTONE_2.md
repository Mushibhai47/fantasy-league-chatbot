# Testing Milestone 2 - Complete System

## System Status

Both servers are running:
- **Backend (FastAPI)**: http://localhost:8000
- **Frontend (Next.js)**: http://localhost:3000

## Test Plan

### 1. Test CSV Upload

1. Open browser to http://localhost:3000
2. You should see the Fantasy Baseball Chatbot homepage with:
   - Beautiful gradient background (blue to orange)
   - Upload area with drag-and-drop
   - Supported formats listed

3. Upload a test CSV:
   - Use `backend/Fantrax_Small_Test.csv` (100 players, fast testing)
   - Drag and drop OR click to browse
   - File name should appear in upload area
   - Click "Upload & Start Chat" button

4. Expected result:
   - Upload completes quickly (bulk insert optimization)
   - Automatically redirects to chat page
   - URL shows `?leagueId=<uuid>`

### 2. Test Chat Interface

After upload completes, you should see:

**Header:**
- "Fantasy Baseball Assistant" title
- Player count stats (e.g., "100 players in roster • X free agents")
- "Show Roster" and "New Upload" buttons

**Chat Area:**
- Welcome message from AI assistant
- Text input box at bottom
- "Send" button
- 3 suggested question buttons

**Test Questions:**

1. **Basic Question:**
   - Type: "Who should I pick up for home runs?"
   - Click Send (or press Enter)
   - AI should respond with specific player recommendations

2. **Use Suggested Question:**
   - Click "Top free agent pitchers" button
   - Message populates in input
   - Click Send
   - AI provides pitcher recommendations

3. **Custom Question:**
   - Type: "What are my roster weaknesses?"
   - AI analyzes your roster and suggests improvements

4. **Player-Specific:**
   - Type: "Tell me about Aaron Judge"
   - AI provides analysis with stats

### 3. Test Roster View

1. Click "Show Roster" button
2. Sidebar appears on right side showing:
   - "My Roster" heading
   - List of players (up to 25)
   - Each player shows:
     - Name
     - Team - Position
     - Projected stats (HR, RBI, SB)

3. Click "Hide" to close sidebar
4. Roster sidebar disappears

### 4. Test Multiple Uploads

1. Click "New Upload" button
2. Returns to homepage
3. Upload a different CSV format:
   - Try `backend/CBS_Small_Test.csv`
   - Should work seamlessly
4. Chat interface loads with new league data

### 5. Test Error Handling

**Invalid File:**
- Try uploading a .txt file
- Should show error: "Please select a CSV file"

**Empty Message:**
- Try clicking Send with no message
- Button should be disabled

## Expected AI Response Quality

The AI should:
- Reference specific player names from your roster/free agents
- Use projection data (HR, RBI, SB, AVG)
- Provide actionable recommendations
- Understand fantasy baseball context
- Format responses clearly

## Known Limitations

1. **Google Sheets Projections:**
   - Currently requires sheet to be public
   - If sheet is private, projections won't load
   - AI still works but without projection data
   - Error logged in backend console

2. **OpenAI API:**
   - Requires valid API key in `.env`
   - If invalid, chat will return generic error message

3. **Database:**
   - Using SQLite (ephemeral for testing)
   - Data resets if database deleted
   - Production should use PostgreSQL

## Backend API Testing

You can also test backend directly:

### 1. API Documentation
Visit: http://localhost:8000/docs
- Interactive Swagger UI
- Test all endpoints
- See request/response schemas

### 2. Test CSV Upload via API
```bash
curl -X POST "http://localhost:8000/csv/upload" \
  -F "file=@backend/Fantrax_Small_Test.csv"
```

### 3. Test Chat via API
```bash
curl -X POST "http://localhost:8000/chat/" \
  -H "Content-Type: application/json" \
  -d '{
    "league_id": "<your-league-id>",
    "message": "Who should I pick up?"
  }'
```

## Performance Expectations

- **CSV Upload**: < 5 seconds for 100 players (bulk insert optimization)
- **Chat Response**: 2-5 seconds (GPT-4 API call)
- **Page Load**: < 1 second
- **Roster View**: Instant toggle

## Troubleshooting

### Frontend won't load
- Check: http://localhost:3000 is accessible
- Check console: `npm run dev` output for errors
- Try: `cd frontend && npm install && npm run dev`

### Backend not responding
- Check: http://localhost:8000 returns FastAPI docs
- Check console: `uvicorn` output for errors
- Try: `cd backend && source venv/bin/activate && python -m uvicorn app.main:app --reload --port 8000`

### AI not responding
- Check: OpenAI API key in `backend/.env`
- Check: Backend logs for "OpenAI" errors
- Verify: API key has credits

### No projections showing
- Check: Google Sheet is public (client needs to do this)
- Check: Backend logs for "projection" errors
- Test URL manually in browser

### Upload fails
- Check: CSV format is valid
- Try: Use provided test CSVs
- Check: Backend logs for parsing errors

## Success Criteria

Milestone 2 is successful if:
- ✅ CSV upload works for all 3 formats (Fantrax, CBS Sports, NFBC)
- ✅ Chat responds with AI-powered recommendations
- ✅ Roster view displays player data
- ✅ Frontend is responsive and user-friendly
- ✅ Performance is acceptable (< 5s uploads, < 5s chat)
- ✅ Error messages are clear and helpful

## Screenshots to Send Client

Take screenshots of:
1. Homepage upload area
2. Successful upload completion
3. Chat interface with AI response
4. Roster sidebar showing players
5. Suggested questions feature

## Next Steps

After successful testing:
1. Get client approval on functionality
2. Request Google Sheet to be made public
3. Proceed with deployment (see DEPLOYMENT_GUIDE.md)
4. Final testing on production environment
5. Request Milestone 2 payment ($800)
