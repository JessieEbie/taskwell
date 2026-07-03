# Taskwell — Self-Hosted Setup Guide

Taskwell is a personal task manager and calendar aggregator that runs as a single HTML file on GitHub Pages, backed by Supabase for data storage and auth. This guide walks through everything needed to stand up your own instance from scratch.

---

## Architecture Overview

| Layer | Technology |
|---|---|
| Frontend | Single `index.html` file hosted on GitHub Pages |
| Database & Auth | Supabase (Postgres + Auth + Edge Functions) |
| Google Calendar | Google Cloud OAuth 2.0 + Calendar API + Gmail API |
| Outlook Calendar | Microsoft Azure OAuth 2.0 + Microsoft Graph API (optional) |
| ICS Feeds | Supabase Edge Function proxy (handles CORS) |

---

## 1. Fork and Deploy to GitHub Pages

1. Fork this repository to your GitHub account.
2. Go to **Settings → Pages** in your fork.
3. Set source to **Deploy from a branch**, branch `main`, folder `/ (root)`.
4. Your app will be live at `https://YOUR_USERNAME.github.io/taskwell/`.

Note your Pages URL — you will need it throughout this guide as the redirect URI.

---

## 2. Supabase Project

### 2a. Create a project

1. Go to [supabase.com](https://supabase.com) and create a new project.
2. Note your **Project URL** and **anon/public key** from **Settings → API**.

### 2b. Enable Google Auth provider

1. In your Supabase dashboard go to **Authentication → Providers → Google**.
2. Enable it and enter your Google OAuth Client ID and Secret (created in step 3 below).
3. Set the **Callback URL** shown there — you will need it when configuring Google Cloud.

### 2c. Create database tables

Run each of these in **SQL Editor → New query**:

```sql
-- Lists
create table public.lists (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users not null,
  name text not null,
  section text default 'Misc',
  context text default 'work',
  created_at timestamptz default now()
);

-- Tasks
create table public.tasks (
  id uuid primary key default gen_random_uuid(),
  list_id uuid references public.lists(id) on delete cascade not null,
  user_id uuid references auth.users,
  title text not null,
  completed boolean default false,
  due_date date,
  week_assigned date,
  created_at timestamptz default now()
);

-- User settings (calendar tokens, feeds, preferences)
create table public.user_settings (
  user_id uuid primary key references auth.users not null,
  cal_feeds jsonb,
  google_tokens jsonb,
  outlook_tokens jsonb,
  outlook_email text,
  timezone text default 'America/Phoenix'
);
```

### 2d. Enable Row Level Security

```sql
-- Enable RLS on all tables
alter table public.lists enable row level security;
alter table public.tasks enable row level security;
alter table public.user_settings enable row level security;

-- Lists: owner only
create policy "owner only" on public.lists
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Tasks: owner only (via list ownership)
create policy "owner only" on public.tasks
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- User settings: each user can read/write only their own row
create policy "owner only" on public.user_settings
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
```

> **Note:** All three tables use the same per-user policy (`auth.uid() = user_id`), so every signed-in user is isolated to their own rows. Who is *allowed to sign in at all* is controlled separately by the `allowed_emails` table, not by RLS. (Do **not** hardcode a single UUID into the `user_settings` policy — that blocks every other account from saving its settings, e.g. Google Calendar tokens, with a `42501` row-level-security error.)

### 2e. Deploy Edge Functions

Three Supabase Edge Functions are required. Install the [Supabase CLI](https://supabase.com/docs/guides/cli) and run `supabase login`, then create each function:

#### `ics-proxy`
Fetches external ICS calendar feeds server-side to avoid browser CORS restrictions.

```typescript
// supabase/functions/ics-proxy/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

serve(async (req) => {
  const url = new URL(req.url).searchParams.get('url')
  const username = new URL(req.url).searchParams.get('username')
  const password = new URL(req.url).searchParams.get('password')
  if (!url) return new Response('Missing url', { status: 400 })

  const headers: Record<string, string> = {}
  if (username && password)
    headers['Authorization'] = 'Basic ' + btoa(`${username}:${password}`)

  const res = await fetch(url, { headers })
  const text = await res.text()
  return new Response(text, {
    headers: {
      'Content-Type': 'text/calendar',
      'Access-Control-Allow-Origin': '*',
    },
  })
})
```

#### `google-calendar-auth`
Handles Google OAuth code exchange and token refresh. Requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` set as Supabase secrets.

```typescript
// supabase/functions/google-calendar-auth/index.ts
import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const CLIENT_ID = Deno.env.get('GOOGLE_CLIENT_ID')!
const CLIENT_SECRET = Deno.env.get('GOOGLE_CLIENT_SECRET')!
const TOKEN_URL = 'https://oauth2.googleapis.com/token'

serve(async (req) => {
  const cors = { 'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json' }
  if (req.method === 'OPTIONS') return new Response(null, { headers: cors })

  const { action, code, code_verifier, redirect_uri, refresh_token } = await req.json()

  if (action === 'exchange') {
    const res = await fetch(TOKEN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        code,
        code_verifier,
        redirect_uri,
      }),
    })
    const data = await res.json()
    return new Response(JSON.stringify(data), { headers: cors })
  }

  if (action === 'refresh') {
    const res = await fetch(TOKEN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: CLIENT_ID,
        client_secret: CLIENT_SECRET,
        refresh_token,
      }),
    })
    const data = await res.json()
    return new Response(JSON.stringify(data), { headers: cors })
  }

  return new Response('Unknown action', { status: 400, headers: cors })
})
```

#### `outlook-calendar-auth` (optional)
Same pattern as `google-calendar-auth` but for Microsoft Graph. Requires `OUTLOOK_CLIENT_ID` and `OUTLOOK_CLIENT_SECRET` as Supabase secrets, and uses `https://login.microsoftonline.com/common/oauth2/v2.0/token`.

Set secrets before deploying:

```bash
supabase secrets set GOOGLE_CLIENT_ID=your_client_id
supabase secrets set GOOGLE_CLIENT_SECRET=your_client_secret

# Deploy all functions
supabase functions deploy ics-proxy
supabase functions deploy google-calendar-auth
supabase functions deploy outlook-calendar-auth
```

---

## 3. Google Cloud Setup

### 3a. Create a project

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Create a new project (e.g. "Taskwell").

### 3b. Enable APIs

In **APIs & Services → Library**, enable:
- **Google Calendar API**
- **Gmail API**

### 3c. Configure OAuth consent screen

1. Go to **Google Auth Platform → Branding** (or **APIs & Services → OAuth consent screen**).
2. Set App name, user support email, and developer contact email.
3. Go to **Audience**, set User type to **External**.
4. Go to **Data Access → Add or remove scopes** and add:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/gmail.send`
5. Add your Google account as a **Test user** initially.
6. Once everything is working, go to **Audience → Publish app** to move to Production (removes the 7-day refresh token expiry).

### 3d. Create OAuth credentials

1. Go to **Clients → Create client**.
2. Application type: **Web application**.
3. Add **Authorized redirect URIs**:
   - `https://YOUR_USERNAME.github.io/taskwell/`
   - Your Supabase auth callback URL (from step 2b)
4. Copy the **Client ID** and **Client Secret**.
   - Client ID goes in `taskwell.html` (safe to be public)
   - Client Secret goes in Supabase as `GOOGLE_CLIENT_SECRET` (never in the HTML)

### 3e. (Optional) Create a dedicated work calendar

If you want a separate Google Calendar for work events:
1. In Google Calendar, create a new calendar (e.g. "Work").
2. Go to its settings and copy the **Calendar ID** (looks like a long `@group.calendar.google.com` address).
3. This becomes `WORK_CAL_ID` in `taskwell.html`.

---

## 4. Outlook Calendar Setup (optional)

Taskwell supports two Outlook integration methods:

### Method A: ICS Feed (read-only, simplest)
1. In Outlook, go to **Settings → Calendar → Shared calendars**.
2. Publish your calendar and copy the ICS link.
3. Add it in the app under **Settings → Calendar → ICS Feeds**.

### Method B: Power Automate (add events from app)
1. Create a Power Automate flow triggered by **"When a new email arrives"**.
2. Filter subject contains `#AddToCalendar`.
3. Parse the email body for `Date:`, `Time:`, `Title:`, `Location:`, `Attendees:`, `Notes:` fields.
4. Use the **Create event (V4)** action to add to your Outlook calendar.
5. In the app under **Settings → Calendar → Work Calendar Email**, enter the email address the flow monitors.

### Method C: Microsoft Graph OAuth (full read/write)
1. Register an app in [portal.azure.com](https://portal.azure.com) → **Azure Active Directory → App registrations**.
2. Add redirect URI: `https://YOUR_USERNAME.github.io/taskwell/`
3. Under **API permissions** add `Calendars.ReadWrite` and `offline_access`.
4. Create a client secret and store it as `OUTLOOK_CLIENT_SECRET` in Supabase secrets.
5. Set `OUTLOOK_CLIENT_ID` in `taskwell.html`.
6. Deploy the `outlook-calendar-auth` edge function.

---

## 5. Configure the HTML

Open `taskwell.html` and update the constants near the top of the `<script>` section:

```javascript
const SB_URL = 'https://YOUR-PROJECT-ID.supabase.co';
const SB_KEY = 'your-supabase-anon-public-key';

const GCAL_CLIENT_ID = 'your-google-oauth-client-id.apps.googleusercontent.com';
const GCAL_REDIRECT  = 'https://YOUR_USERNAME.github.io/taskwell/';
const WORK_CAL_ID    = 'your-work-calendar-id@group.calendar.google.com'; // optional

const OUTLOOK_CLIENT_ID = 'your-azure-app-client-id'; // optional
const OUTLOOK_REDIRECT  = 'https://YOUR_USERNAME.github.io/taskwell/';
```

Then copy `taskwell.html` to `index.html` and push both to GitHub.

---

## 6. First Login

1. Open `https://YOUR_USERNAME.github.io/taskwell/`.
2. Click **Sign in with Google** and complete the OAuth flow.
3. You will be redirected back to the app.
4. Go to **Settings → Calendar** in the app to connect Google Calendar and add any ICS feeds.

> **Controlling who can sign in:** access is gated by the `allowed_emails` table, not by hardcoding a UUID into RLS. Add the Google email addresses you want to allow: `insert into public.allowed_emails (email) values ('you@gmail.com');`. RLS (`auth.uid() = user_id`) then keeps each allowed user isolated to their own rows.

---

## 7. Security Notes

- The **Supabase anon key** is safe to include in the HTML — it is a publishable key and Supabase's RLS policies enforce all data access.
- The **Google client secret** and **Outlook client secret** must never be in the HTML. They live only in Supabase Edge Function secrets.
- The **Supabase service role key** must never be committed anywhere.
- RLS (`auth.uid() = user_id`) isolates every user to their own rows, so no signed-in user can read or write another user's data — including yours.
- Who is allowed to sign in at all is controlled by the `allowed_emails` table. Anyone not listed there is shown "Access denied" and signed out.

---

## 8. Updating the App

After making changes to `taskwell.html`:

```bash
cp taskwell.html index.html
git add taskwell.html index.html
git commit -m "your message"
git push
```

GitHub Pages will redeploy automatically within a minute or two. If changes don't appear, do a hard refresh (`Cmd+Shift+R` / `Ctrl+Shift+R`) to clear the browser cache.
