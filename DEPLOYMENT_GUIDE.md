# 🚀 SwapSkills Deployment Guide: Vercel & Free Cloud Architecture

This guide walks you through deploying **SwapSkills** to production.

---

## 🏗️ Architecture Overview

| Component | Recommended Free Provider | Alternative | Cost |
| :--- | :--- | :--- | :--- |
| **Frontend & Flask App** | **Vercel** (Serverless Python WSGI) | **Render** or **Railway** | 100% Free |
| **Database** | **Supabase** / **Neon** (PostgreSQL) | Local SQLite / MongoDB Atlas | 100% Free |
| **Media / File Storage** | **Cloudinary** / **Supabase Storage** | Local Disk / AWS S3 Free Tier | 100% Free |

---

## 📋 Pre-Flight Checklist (Already Prepared in Your Project)

1. [x] **`vercel.json`** configured with `@vercel/python` routing:
   ```json
   {
     "version": 2,
     "builds": [{ "src": "run.py", "use": "@vercel/python" }],
     "routes": [{ "src": "/(.*)", "dest": "/run.py" }]
   }
   ```
2. [x] **`requirements.txt`** contains `Flask`, `gunicorn`, `Flask-SQLAlchemy`, and dependencies.
3. [x] **`.gitignore`** cleaned up (`run.py` included, secrets excluded).

---

## 🛠️ Step-by-Step Guide

### Step 1: Initialize Git and Push to GitHub

Open a terminal in your project directory:

```bash
cd /home/jai/Downloads/FINAL-PROJECT/SwapSkills

# 1. Initialize Git repository (if not already done)
git init

# 2. Add all files to staging
git add .

# 3. Commit your changes
git commit -m "Production release: Smart matching, study sessions, library hub, and clean auth"

# 4. Link your GitHub repository
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/SwapSkills.git

# 5. Push to GitHub
git push -u origin main
```

---

### Step 2: Deploy to Vercel (Frontend & Web App)

#### Option A: Via Vercel Web Dashboard (Easiest)
1. Go to [vercel.com](https://vercel.com) and log in with your GitHub account.
2. Click **"Add New..."** &rarr; **"Project"**.
3. Under **Import Git Repository**, select your `SwapSkills` repository.
4. **Project Settings**:
   - **Framework Preset**: Other
   - **Root Directory**: `./` (leave default)
5. **Environment Variables** (Add under "Environment Variables"):
   - `SECRET_KEY`: `your-random-production-secret-key-12345`
   - `DATABASE_URL`: *(Your cloud PostgreSQL connection string from Step 3, optional)*
   - `MAX_CONTENT_LENGTH_MB`: `500`
6. Click **Deploy**. Vercel will install dependencies and provide you a live URL (e.g., `https://swapskills.vercel.app`).

#### Option B: Via Vercel CLI (From Terminal)
```bash
# Install Vercel CLI globally
npm i -g vercel

# Run deployment from project folder
vercel

# For production deployment:
vercel --prod
```

---

### Step 3: Cloud Database Setup (Free PostgreSQL)

To preserve sessions, users, and resources permanently across serverless instances:

1. **Create Free Database**:
   - Go to [Neon.tech](https://neon.tech) or [Supabase.com](https://supabase.com).
   - Sign up for a free tier database.
   - Copy your connection URI (e.g., `postgresql://user:password@ep-sample.neon.tech/swapskills?sslmode=require`).
2. **Add to Vercel Environment Variables**:
   - Name: `DATABASE_URL`
   - Value: `postgresql://user:password@ep-sample.neon.tech/swapskills?sslmode=require`
3. SwapSkills will automatically switch its storage engine to PostgreSQL via SQLAlchemy.

---

### Step 4: Alternative Host — Render.com (Persistent Web Service Alternative)

If you prefer a persistent non-serverless server:
1. Go to [render.com](https://render.com).
2. Click **New +** &rarr; **Web Service**.
3. Connect your GitHub repository.
4. Set:
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app`
5. Click **Create Web Service**.
