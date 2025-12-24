# Upload Error Fix - Summary

## Issue
Upload was succeeding on backend (200 OK) but frontend was showing "Failed to upload CSV" error.

## Changes Made

### 1. Backend Schema Fix (`backend/app/schemas/league.py`)
**Problem**: UUID objects weren't being properly serialized to JSON strings.

**Fix**: Added `json_encoders` config to Pydantic models:
```python
class LeagueResponse(BaseModel):
    # ... fields ...
    class Config:
        from_attributes = True
        json_encoders = {
            UUID: str  # Ensure UUID is serialized as string
        }
```

### 2. Frontend Debugging (`frontend/app/page.tsx`)
**Added**: Console logging to see actual error and response:
```typescript
try {
    console.log('Starting upload...');
    const response: LeagueResponse = await uploadCSV(file);
    console.log('Upload response:', response);
    console.log('League ID:', response.id);
    // ... rest of code
} catch (err: any) {
    console.error('Upload error:', err);
    console.error('Error response:', err.response);
    // ... error handling
}
```

## How to Test

### 1. Both Servers Running
- **Backend**: [http://localhost:8000](http://localhost:8000)
- **Frontend**: [http://localhost:3000](http://localhost:3000)

### 2. Upload Test File
1. Open browser to [http://localhost:3000](http://localhost:3000)
2. Upload: `backend/NFBC_Small_Test.csv` (or any test CSV)
3. Click "Upload & Start Chat"

### 3. Check Browser Console (F12)
With the debug logging added, you'll now see:
```
Starting upload...
Upload response: {id: "...", league_type: "nfbc", ...}
League ID: <uuid-string>
```

If there's an error, you'll see:
```
Upload error: <error object>
Error response: <response data>
```

### 4. Expected Behavior
- ✅ Upload should complete successfully
- ✅ Redirect to chat page: `http://localhost:3000/chat?leagueId=<uuid>`
- ✅ No error message shown
- ✅ Backend logs show 200 OK
- ✅ Frontend console shows successful upload

## What Was Fixed

1. **UUID Serialization**: Pydantic now explicitly converts UUID objects to strings in JSON responses
2. **Debugging**: Added console logging to see exactly what's happening in the upload flow
3. **RosterResponse Fix**: Also updated RosterResponse schema with same UUID encoding

## Files Modified

1. `backend/app/schemas/league.py` - Added json_encoders config
2. `frontend/app/page.tsx` - Added console.log debugging

## Next Steps

1. Test the upload with browser console open (F12)
2. Check console logs to see if upload succeeds
3. If still showing error, console will show exact error message
4. Once working, remove console.log statements (or keep for production debugging)
