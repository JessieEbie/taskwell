# Adding Taskwell events to a managed Outlook calendar

Some work and school Outlook / Microsoft 365 calendars don't let outside apps connect to them. This guide sets up a small **Power Automate** flow so Taskwell can still add events to one of those calendars.

You don't need to be technical to do this — just follow the steps in order. It takes about 10–15 minutes, and you only do it once.

---

## How it works (the short version)

1. In Taskwell, you create a **Work** event as normal.
2. Taskwell sends an email from your connected **Google account** to your **Outlook inbox**. The subject line starts with `#AddToCalendar`.
3. A **Power Automate flow** watches your Outlook inbox. When it sees that email, it reads the event details and adds the event to your Outlook calendar automatically.

So the pieces you need are: a Google account connected in Taskwell (for sending), an Outlook/Microsoft 365 account (for receiving), and the flow below (the part that files the event).

---

## What you need before you start

- **Taskwell**, signed in, with **Google Calendar connected** (Settings → Calendar → *Connect Google Calendar*). This is what sends the emails.
- An **Outlook / Microsoft 365 account** that can use **Power Automate** (most work and school accounts can — go to [make.powerautomate.com](https://make.powerautomate.com) and sign in to check).
- The importable flow file: **[download it here](https://raw.githubusercontent.com/JessieEbie/taskwell/main/OutlookAutomatorTaskwellEventGenerator_20260630014511.zip)** (save it somewhere easy to find, like your Downloads folder). Don't unzip it — you import the `.zip` as-is.

---

## Step 1 — Import the flow

1. Go to **[make.powerautomate.com](https://make.powerautomate.com)** and sign in with your Outlook/Microsoft 365 account.
2. In the left menu, click **My flows**.
3. Click **Import** (top of the page) → **Import Package (Legacy)**.
4. Click **Upload** and choose the `.zip` file you downloaded.
5. Power Automate will show a list of items to import and a section called **Related resources** — these are the connections the flow uses (usually **Office 365 Outlook**).

## Step 2 — Connect it to your own account

In that same import screen, each related resource needs to point at **your** account:

1. Next to each connection, click **Select during import** (or the wrench/"Update" link).
2. Choose your own **Office 365 Outlook** connection. If none exists yet, click **Create new**, then follow the prompt to sign in and allow access.
3. Once every connection shows a green check (or your account name), click **Import** at the bottom.

Power Automate will say the import succeeded.

## Step 3 — Turn the flow on and check the trigger

1. Go back to **My flows** and open the newly imported flow (it will have "Taskwell" or "Event Generator" in the name).
2. Make sure it's **turned on** — if you see a **Turn on** button, click it.
3. Open the flow's first step (the trigger, **"When a new email arrives"**). Confirm:
   - It's watching the **inbox of the Outlook account you want events added to**.
   - It filters for a **subject that contains** `#AddToCalendar`. (This is already set in the file — just confirm it's there.)
4. Open the step that **creates the calendar event** and confirm the **Calendar** it points to is the one you want events on. Change it if needed, then **Save**.

## Step 4 — Tell Taskwell which inbox to email

1. In Taskwell, go to **Settings → Calendar → Add to a Managed Outlook Calendar**.
2. Enter the **email address of the Outlook inbox the flow is watching** (the same account from Step 3) and click **Save**.

That's the address Taskwell will send `#AddToCalendar` emails to.

---

## Test it

1. In Taskwell, create a new **Work** event (any title, later today).
2. Within a minute or two, check the Outlook calendar you chose in Step 3 — the event should appear.
3. If it doesn't show up, see Troubleshooting below.

---

## Troubleshooting

**Nothing appears on the Outlook calendar.**
- Open the flow in Power Automate → click the **Run history**. Each incoming email should show a run.
  - **No runs at all?** The email isn't reaching the watched inbox. Double-check the address you entered in Taskwell (Step 4) exactly matches the inbox the flow watches (Step 3), and look in that inbox's **Junk** folder for the `#AddToCalendar` email.
  - **A run that failed (red X)?** Click it to see which step failed. Usually it's a connection that needs re-authorizing — click the step, reconnect your Outlook account, and save.

**Taskwell shows a Gmail permission error when creating a Work event.**
- Reconnect Google in Taskwell: **Settings → Calendar → Reconnect / switch account**, and make sure you tap **Allow** on every permission (Taskwell needs permission to send email on your behalf).

**The event lands at the wrong time.**
- Check your timezone in **Taskwell → Settings → Calendar → Timezone**.

**I want to stop it.**
- Turn the flow **off** in Power Automate (My flows → ⋯ → Turn off), or remove the email in Taskwell (Settings → Calendar → *Remove*).
