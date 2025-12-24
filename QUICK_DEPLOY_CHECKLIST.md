# Quick Deployment Checklist

## ✅ Pre-Deployment Done
- [x] Backend code complete
- [x] Frontend code complete
- [x] Projection API working
- [x] Dollar values displaying
- [x] Local testing successful

## 📝 What You Need to Do

### 1. Create GitHub Account (if you don't have one)
- Go to https://github.com/join
- Sign up (it's free)

### 2. Push Code to GitHub (5 minutes)
```bash
cd C:\Users\DELL\Downloads\Rudy\fantasy-league-chatbot
git init
git add .
git commit -m "Milestone 2 complete"
git remote add origin https://github.com/YOUR_USERNAME/fantasy-league-chatbot.git
git push -u origin main
```

### 3. Deploy Backend to Railway (7 minutes)
- Sign up: https://railway.app (use GitHub login)
- New Project → Deploy from GitHub
- Select your repo
- Set root directory to: `backend`
- Add environment variables (copy from `.env` file)
- Generate domain → Save the URL!

### 4. Deploy Frontend to Vercel (5 minutes)
- Sign up: https://vercel.com (use GitHub login)
- Import your repo
- Set root directory to: `frontend`
- Add environment variable:
  - `NEXT_PUBLIC_API_URL` = your Railway URL + `/api`
- Deploy!

### 5. Update CORS (1 minute)
- Go back to Railway
- Update `FRONTEND_URL` to your Vercel URL
- Redeploy

### 6. Test & Share (2 minutes)
- Visit your Vercel URL
- Upload CSV
- Ask test question
- Share URL with Rudy!

## ⏱️ Total Time: ~20 minutes

## 💰 Total Cost: $0 (both services are free!)

---

## Need Help?

Read the full guide: [DEPLOYMENT_STEPS.txt](DEPLOYMENT_STEPS.txt)

Or just follow the steps - they're pretty straightforward!

Good luck! 🚀
