# Fantasy League Chatbot - Deployment Instructions

## 🎉 Milestone 2 Complete!

All features are working:
- CSV Upload (Fantrax, CBS, NFBC)
- AI Chat with GPT-4
- Razzball Projection API integration
- $ Dollar values in responses
- React frontend

## 🚀 Deploy to Production (Free!)

Follow these simple steps to get Rudy a live URL to test:

### Option 1: Quick Deploy (~20 minutes)
1. Read: `QUICK_DEPLOY_CHECKLIST.md`
2. Follow: `DEPLOYMENT_STEPS.txt`
3. Done!

### What You'll Get
- **Backend URL:** https://your-app.railway.app (Railway)
- **Frontend URL:** https://your-app.vercel.app (Vercel)
- **Cost:** $0/month (both are free!)

### What Rudy Will See
A live website where he can:
1. Upload his league CSV
2. Chat with AI about his roster
3. Get recommendations with $ dollar values
4. Test all the Milestone 2 features

## 📁 Files Ready for Deployment

### Backend (Railway)
- ✅ `backend/Procfile` - Railway start command
- ✅ `backend/railway.json` - Railway configuration
- ✅ `backend/requirements.txt` - All Python packages
- ✅ `backend/.env.example` - Environment variables template

### Frontend (Vercel)
- ✅ `frontend/package.json` - All Node packages
- ✅ `frontend/next.config.js` - Next.js configuration
- ✅ `frontend/lib/api.ts` - Uses NEXT_PUBLIC_API_URL

### Security
- ✅ `.gitignore` - Excludes .env and sensitive files
- ✅ Private GitHub repo recommended

## 🔑 Environment Variables Needed

### Backend (Railway)
```
DATABASE_URL=sqlite:///./fantasy_chatbot.db
RAZZBALL_API_KEY=71yqx5zf-be81-2a2c-860p-oxch3odcgszm
RAZZBALL_API_BASE_URL=https://api.razzball.com/mlb
PLAYER_REFERENCE_URL=https://razzball.com/mlbamidsshhh/
SECRET_KEY=your-random-secret-key
ALGORITHM=HS256
FRONTEND_URL=https://your-vercel-url.vercel.app
OPENAI_API_KEY=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
ENVIRONMENT=production
```

### Frontend (Vercel)
```
NEXT_PUBLIC_API_URL=https://your-railway-url.up.railway.app/api
```

## 📝 Deployment Checklist

- [ ] GitHub account created
- [ ] Code pushed to private GitHub repo
- [ ] Railway account created (with GitHub)
- [ ] Backend deployed to Railway
- [ ] Environment variables added to Railway
- [ ] Railway domain generated
- [ ] Vercel account created (with GitHub)
- [ ] Frontend deployed to Vercel
- [ ] NEXT_PUBLIC_API_URL added to Vercel
- [ ] FRONTEND_URL updated in Railway
- [ ] Tested live URL
- [ ] Shared URL with Rudy

## 🧪 Test the Deployment

1. Visit your Vercel URL
2. Upload: `Csvs/Fantrax_Small_Test.csv`
3. Ask: "Who are the top 10 most valuable free agent hitters and pitchers?"
4. Verify: Should see Geraldo Perdomo at $27.9, Trevor Rogers at $14.6, etc.

## 📧 Message for Rudy

```
Hi Rudy!

The chatbot is now live and ready for you to test:

🔗 URL: https://your-vercel-url.vercel.app

How to test:
1. Upload your league CSV (Fantrax, CBS, or NFBC format)
2. Ask questions about your roster
3. Get AI-powered recommendations with $ dollar values!

Try this question:
"Who are the top 10 most valuable free agent hitters and pitchers?"

You should see players sorted by $ value from your Razzball projection API!

Let me know what you think!
```

## ⚠️ Important Notes

1. **Keep .env file local** - Never push it to GitHub
2. **Use private GitHub repo** - To protect API keys
3. **Test before sharing** - Make sure projections work
4. **Free tiers** - Railway: 500 hours/month, Vercel: unlimited

## 🆘 Need Help?

- Check `DEPLOYMENT_STEPS.txt` for detailed instructions
- Railway logs: Dashboard → Your service → Deployments → View Logs
- Vercel logs: Dashboard → Your project → Deployments → Runtime Logs

## 🎯 Next Steps (After Rudy Approves)

- Collect Milestone 2 payment ($800)
- Discuss Milestone 3 features:
  - Admin panel
  - User management
  - Conversation history
  - Custom branding
  - Training/fine-tuning

Good luck with the deployment! 🚀
