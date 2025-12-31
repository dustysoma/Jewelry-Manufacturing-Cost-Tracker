# Railway Deployment Guide for Jewelry MFG App

## Quick Start (5 minutes)

### Step 1: Push to GitHub
1. Go to [github.com/new](https://github.com/new) and create a new public repo (e.g., `jewelry-mfg`)
2. In your project folder, run:
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/jewelry-mfg.git
git push -u origin main
```

### Step 2: Deploy to Railway
1. Go to [railway.app](https://railway.app) (you're already logged in)
2. Click **"New Project"** → **"Deploy from GitHub"**
3. Select your `jewelry-mfg` repository
4. Railway will auto-detect it's a Python app and start deploying!

### Step 3: Set Environment Variables
1. In Railway dashboard, go to your project → **"Variables"**
2. Add these variables:
   - `METALS_DEV_API_KEY` = your API key from [metals.dev](https://metals.dev)
   - `BASE_CURRENCY` = `USD`

Railway automatically provides `DATABASE_URL` (PostgreSQL).

### Step 4: Access Your App
1. Go to **"Deployments"** in Railway
2. Click the generated URL (e.g., `https://jewelry-mfg-production.up.railway.app`)
3. Visit `/ui` to access the app

---

## Connect Your Domain (iqstudiola.com)

### In Railway:
1. Go to your project → **"Settings"** → **"Domains"**
2. Click **"Add Domain"**
3. Enter: `iqstudiola.com` (or `jewelry.iqstudiola.com`)

### In Hostinger DNS:
1. Log into Hostinger → DNS Zone
2. Add a CNAME record pointing to Railway (Railway will show you the exact value)
3. Wait 5-10 minutes for DNS to propagate

---

## Database Notes
- **Local Development**: Uses SQLite (`jewelry.db`)
- **Railway Production**: Automatically uses PostgreSQL
- First deploy will auto-create tables

## Troubleshooting

**App won't start?**
- Check Railway logs: Dashboard → Deployments → View logs
- Verify env variables are set

**Database errors?**
- Railway Postgres is auto-provisioned
- Tables are created on first startup

**Domain not working?**
- Wait for DNS propagation (5-30 minutes)
- Check CNAME record in Hostinger is correct

---

Need help? Check Railway docs at [railway.app/docs](https://docs.railway.app)
