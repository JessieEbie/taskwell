# Taskwell — Self-Hosted Setup Guide

Taskwell is a personal task manager and calendar aggregator. It runs as a single hosted app at `https://jessieebie.github.io/taskwell/`, backed by Supabase for data storage and auth.

**You do not need to fork this repository, deploy your own copy, or edit any code to self-host.** The app has a built-in setup wizard that connects it to *your own* free Supabase project instead of the shared one — your data stays fully separate, and you keep using the same web address. This guide covers that process end-to-end, including the parts the wizard doesn't automate (Edge Functions and Google Calendar OAuth).

---

## Architecture Overview

| Layer | Technology |
|---|---|
| Frontend | The single hosted app at `jessieebie.github.io/taskwell/` — no deployment needed |
| Database & Auth | Your own Supabase project (Postgres + Auth + Edge Functions) |
| Google Calendar | Google Cloud OAuth 2.0 + Calendar API + Gmail API |
| Outlook Calendar | Microsoft Azure OAuth 2.0 + Microsoft Graph API (optional), or Power Automate, or an ICS feed |
| ICS Feeds | A Supabase Edge Function proxy (handles CORS) |

---

## 1. Create a Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a free project.
2. Leave **Enable Data API**, **Automatically expose new tables**, and **Enable automatic RLS** at their defaults — the setup script in the next step creates your tables and security policies, so there's nothing extra to configure here.
3. Note your **Project ID** (the subdomain in your dashboard's URL, e.g. `abcdefghijklmnop` from `abcdefghijklmnop.supabase.co`) and your **anon/publishable key** (Project Settings → API). You'll need both shortly.

---

## 2. Run the Setup Wizard

1. Open `https://jessieebie.github.io/taskwell/`.
2. On the sign-in screen, click **"Set up your own self-hosted Taskwell instance →"**.
3. Follow the wizard on screen — it walks you through:
   - Pasting and running the provided SQL script in your Supabase **SQL Editor** (creates your tables, row-level security policies, and an `allowed_emails` table)
   - Adding your own email (and anyone else's you want to let in) to `allowed_emails` — this is what controls who can sign in at all; skip it and you'll be locked out of your own instance
   - Setting your Supabase **Authentication → URL Configuration** (Site URL and Redirect URLs) — required, or sign-in will redirect to `localhost` and fail
   - Setting up **Google Sign-In** (a Google Cloud project, OAuth consent screen, and OAuth client) — required even if you don't plan to use Calendar features, since this is what lets you sign in at all
   - Entering your Project ID and anon key and clicking **Save & Continue**

Once saved, this browser is now pointed at your own Supabase project. Sign in with your Google account to finish.

> Use **"Try in this tab only"** instead of **"Save & Continue"** if you just want to test your setup without affecting your normal Taskwell sign-in on other tabs of this same browser.

The rest of this guide covers optional features the wizard doesn't set up for you: connecting Google Calendar, and Outlook integration.

---

## 3. Google Calendar Setup (optional)

Only needed if you want Taskwell to create/edit events on a Google Calendar — viewing a calendar only requires an ICS feed (Settings → Calendar in the app), no setup below is needed for that.

### 3a. Enable APIs

In your Google Cloud project (the same one from the sign-in setup, or a new one) — **APIs & Services → Library** — enable:
- **Google Calendar API**
- **Gmail API**

### 3b. Add Calendar/Gmail scopes to your OAuth consent screen

1. Go to **Google Auth Platform → Data Access** (or **APIs & Services → OAuth consent screen → Data Access**).
2. Click **Add or remove scopes** and add:
   - `https://www.googleapis.com/auth/calendar`
   - `https://www.googleapis.com/auth/gmail.send`
3. Save.

### 3c. Create a dedicated OAuth client for Calendar

The Calendar connection uses its own OAuth client, separate from the one used for signing in.

1. Go to **Google Auth Platform → Clients → Create Client**.
2. Application type: **Web application**.
3. Under **Authorized redirect URIs**, add: `https://jessieebie.github.io/taskwell/`
4. Click **Create**. Copy the **Client ID** and **Client Secret**.
5. While your app is in **Testing** status, add every Google account that should be able to connect Calendar under **Audience → Test users** (Google auto-expires refresh tokens for testing apps after 7 days — publish to Production once everything works to remove this limit).

### 3d. Deploy the Edge Functions

Two Supabase Edge Functions handle Calendar and ICS feeds. The easiest way to deploy them is directly in the Supabase Dashboard — no command-line tools required:

1. In your Supabase project, click **Edge Functions** in the left sidebar → **Deploy a new function** → **Via Editor**.
2. Create a function named `google-calendar-auth`, paste in the code below, and deploy.
3. Create a second function named `ics-proxy`, paste in that code, and deploy.
4. Go to **Edge Functions → Secrets** and add:
   - `GOOGLE_CLIENT_ID` = the Client ID from step 3c
   - `GOOGLE_CLIENT_SECRET` = the Client Secret from step 3c

#### `google-calendar-auth`

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const CLIENT_ID = Deno.env.get("GOOGLE_CLIENT_ID")!;
const CLIENT_SECRET = Deno.env.get("GOOGLE_CLIENT_SECRET")!;

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return new Response("Unauthorized", { status: 401, headers: CORS });

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } }
  );
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) {
    return new Response("Forbidden", { status: 403, headers: CORS });
  }

  const { action, code, code_verifier, redirect_uri, refresh_token } = await req.json();

  let body: Record<string, string>;
  if (action === "exchange") {
    body = { code, client_id: CLIENT_ID, client_secret: CLIENT_SECRET,
             redirect_uri, grant_type: "authorization_code", code_verifier };
  } else if (action === "refresh") {
    body = { refresh_token, client_id: CLIENT_ID, client_secret: CLIENT_SECRET,
             grant_type: "refresh_token" };
  } else {
    return new Response("Unknown action", { status: 400, headers: CORS });
  }

  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
  });
  const result = await r.json();
  if (!r.ok) return new Response(JSON.stringify(result), { status: 400, headers: CORS });
  return new Response(JSON.stringify(result), { headers: { ...CORS, "Content-Type": "application/json" } });
});
```

#### `ics-proxy`

Fetches external ICS calendar feeds server-side to avoid browser CORS restrictions. Required for the ICS Feeds feature in Settings → Calendar.

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: CORS });

  const authHeader = req.headers.get("Authorization");
  if (!authHeader) return new Response("Unauthorized", { status: 401, headers: CORS });

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_ANON_KEY")!,
    { global: { headers: { Authorization: authHeader } } }
  );
  const { data: { user }, error } = await supabase.auth.getUser();
  if (error || !user) {
    return new Response("Forbidden", { status: 403, headers: CORS });
  }

  const targetUrl = new URL(req.url).searchParams.get("url");
  if (!targetUrl) return new Response("Missing url param", { status: 400, headers: CORS });

  try {
    const params = new URL(req.url).searchParams;
    const clean = targetUrl.replace(/^webcal:\/\//i, "https://");
    const fetchHeaders: Record<string, string> = {
      "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    };
    const username = params.get("username");
    const password = params.get("password");
    if (username) {
      fetchHeaders["Authorization"] = "Basic " + btoa(`${username}:${password ?? ""}`);
    }
    const res = await fetch(clean, { headers: fetchHeaders });
    const text = await res.text();
    if (!text.includes("BEGIN:VCALENDAR")) throw new Error("Not a valid ICS feed");
    return new Response(text, { headers: { ...CORS, "Content-Type": "text/calendar; charset=utf-8" } });
  } catch (e) {
    return new Response(e.message, { status: 502, headers: CORS });
  }
});
```

### 3e. Connect it

Back in the app: **Settings → Calendar → Connect Google Calendar**, sign in, and allow the requested permissions.

Want Work events to land on a different calendar than your main one? Settings → Calendar → **"Second calendar account"** lets you add a second Calendar ID and tag it Work or Personal — no code changes needed.

---

## 4. Outlook Calendar Setup (optional)

Taskwell supports three ways to work with Outlook:

### Method A: ICS Feed (view-only, simplest)
1. In Outlook, go to **Settings → Calendar → Shared calendars**.
2. Publish your calendar and copy the ICS link.
3. Add it in the app under **Settings → Calendar → ICS Feeds**.

### Method B: Power Automate (add events from the app)
For a managed work/school Outlook calendar you can't connect to directly.
1. Create a Power Automate flow triggered by **"When a new email arrives."**
2. Filter subject contains `#AddToCalendar`.
3. Parse the email body for `Date:`, `Time:`, `Title:`, `Location:`, `Attendees:`, `Notes:` fields.
4. Use the **Create event (V4)** action to add to your Outlook calendar.
5. In the app under **Settings → Calendar → "Add to a Managed Outlook Calendar,"** enter the email address the flow monitors.

### Method C: Microsoft Graph OAuth (full read/write, advanced)
1. Register an app in [portal.azure.com](https://portal.azure.com) → **Azure Active Directory → App registrations**.
2. Add redirect URI: `https://jessieebie.github.io/taskwell/`
3. Under **API permissions** add `Calendars.ReadWrite` and `offline_access`.
4. Create a client secret and store it as `OUTLOOK_CLIENT_SECRET` in your Supabase Edge Function secrets (alongside `OUTLOOK_CLIENT_ID`).
5. Deploy an `outlook-calendar-auth` Edge Function following the same pattern as `google-calendar-auth` above, but pointed at `https://login.microsoftonline.com/common/oauth2/v2.0/token`.

---

## 5. Security Notes

- Your Supabase **anon/publishable key** is safe to have entered into the app — it's a publishable key, and Supabase's row-level security policies (created by the setup script) enforce all data access.
- Your Google/Outlook **client secrets** must never go anywhere except Supabase Edge Function secrets — never paste them into the app itself.
- Never generate or share your Supabase **service role key** — Taskwell never needs it.
- The setup script's row-level security means every signed-in user can only read/write their own rows, including you.
- Who can sign in at all is controlled by the `allowed_emails` table (added during setup) — enforced on the server, not just in the app, so it can't be bypassed by calling the API directly. Add or remove people any time via the Table Editor.
- While your Google Cloud project is in **Testing** status, Google adds a second layer: only people you've added under **Test users** can even complete the sign-in screen. Publishing to Production removes that limit — but `allowed_emails` still gates actual access either way, so publishing is safe to do once things work.

---

## Keeping Up to Date

Since you're using the same hosted app (not a copy of the code), improvements Jessie makes are available to you automatically — there's nothing to update or redeploy yourself.
