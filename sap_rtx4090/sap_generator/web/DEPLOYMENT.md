# SAP Generator Deployment Guide

## Architecture

```
┌─────────────────┐         ┌─────────────────┐         ┌─────────────────┐
│     VERCEL      │   API   │     RENDER      │   DB    │    SUPABASE     │
│    Frontend     │────────▶│    Backend      │────────▶│   PostgreSQL    │
│    Next.js      │         │    FastAPI      │         │                 │
└─────────────────┘         └─────────────────┘         └─────────────────┘
```

---

## Step 1: Set Up Supabase Database

### 1.1 Go to Supabase Dashboard
Your project: https://supabase.com/dashboard/project/tnydsoojcoucmnxyfdsk

### 1.2 Run Database Schema
1. Go to **SQL Editor** in the left sidebar
2. Copy the contents of `database/schema.sql`
3. Click **Run** to create the tables

### 1.3 Get Service Role Key
1. Go to **Settings** → **API**
2. Copy the **service_role** key (NOT the anon key)
3. Save it for Step 2

---

## Step 2: Deploy Backend to Render

### 2.1 Create Render Account
Go to https://render.com and sign up (free)

### 2.2 Create New Web Service
1. Click **New** → **Web Service**
2. Connect your GitHub repo
3. Configure:

| Setting | Value |
|---------|-------|
| Name | `sap-generator-api` |
| Root Directory | `web/backend` |
| Environment | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

### 2.3 Add Environment Variables
In Render dashboard, add these:

```
SUPABASE_URL=https://tnydsoojcoucmnxyfdsk.supabase.co
SUPABASE_SERVICE_KEY=<your_service_role_key>
GROQ_API_KEY=<your_groq_key>
FRONTEND_URL=https://your-app.vercel.app
```

### 2.4 Deploy
Click **Create Web Service** and wait for deployment.

Copy the URL (e.g., `https://sap-generator-api.onrender.com`)

---

## Step 3: Deploy Frontend to Vercel

### 3.1 Install Vercel CLI (Optional)
```bash
npm i -g vercel
```

### 3.2 Deploy via GitHub (Recommended)
1. Go to https://vercel.com
2. Click **Add New** → **Project**
3. Import your GitHub repo
4. Configure:

| Setting | Value |
|---------|-------|
| Framework Preset | `Next.js` |
| Root Directory | `web/frontend` |

### 3.3 Add Environment Variables
In Vercel project settings, add:

```
NEXT_PUBLIC_API_URL=https://sap-generator-api.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://tnydsoojcoucmnxyfdsk.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=sb_publishable_xoXfAVXSNtOtArRk4Ksz9w_zcGq1hE9
```

### 3.4 Deploy
Click **Deploy** and wait for build to complete.

---

## Step 4: Update CORS

Go back to Render and update `FRONTEND_URL` with your Vercel URL:
```
FRONTEND_URL=https://your-app.vercel.app
```

---

## Local Development

### Backend
```bash
cd web/backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys
uvicorn main:app --reload
```

### Frontend
```bash
cd web/frontend
npm install
npm run dev
```

---

## Troubleshooting

### Backend sleeping on Render free tier
Render free tier sleeps after 15 minutes. First request takes ~30s to wake up.

**Solution**: Upgrade to $7/month for always-on, or use a cron job to ping the health endpoint.

### CORS errors
Make sure `FRONTEND_URL` in Render matches your Vercel URL exactly.

### Database connection issues
Make sure you're using the **service_role** key (not anon key) in the backend.

---

## URLs

| Service | URL |
|---------|-----|
| Supabase Dashboard | https://supabase.com/dashboard/project/tnydsoojcoucmnxyfdsk |
| Render Dashboard | https://dashboard.render.com |
| Vercel Dashboard | https://vercel.com/dashboard |
