# Focus and anti-avoidance features — plan

Paused 2026-11-03, ready to build. Nothing has been changed in the app yet.

## What this is for

Juggling about ten things at once at work makes it hard to focus and easy to
dodge the hard ones. These four features are meant to narrow the field and
lower the cost of starting.

Build order: 1 and 2 first, then reassess. Web app first — the Mac app picks
it up automatically (see below).

## The four features, as specified

1. **Focus mode.** Pick one task from Hub or Week. The screen shows only that
   task plus a simple timer. Everything else is hidden until finished or
   exited. The timer is framed as "work for 10 minutes, then you're free to
   stop."

2. **Parking lot.** A one-tap quick capture inside focus mode for stray
   thoughts ("I should also do X"). It sends the thought to the Capture inbox
   and returns to the task. It must be clear the thought will show up in the
   Week view, so it's trustworthy enough to let go of.

3. **Dreaded flag and "shrink it."** Mark a task as dreaded, and Taskwell
   suggests a tiny, almost-too-easy first step (for example, "open the
   document and write one ugly sentence"). Dreaded tasks that have sat the
   longest can float up on the Hub.

4. **Pick three.** Each morning, choose at most three work tasks for the day
   so the rest stop competing for attention.

## Design principles (these are constraints, not decoration)

- Calm. No red overdue counts, no broken streaks, no scolding language.
- Nudges are gentle, never demands.
- A quiet "done today" list, so the day shows what was actually finished.
- Keep the warm cream / dusty rose look.
- Touch and Apple Pencil Scribble both have to work.

Concrete commitments that follow from those:

- `--rust` already means overdue and in-progress. None of these features use
  it, or any other red. They use `--sage` and `--khaki`.
- Focus mode never shows a count of what is still undone.
- The timer never alarms or nags.

## What the existing code already gives us

- **Focus mode already exists, but for lists.** `focusedListId`,
  `openListFocus()`, and `renderFocusedList()` swap the Hub's contents for one
  list. Task focus is a sibling of this. Reuse the pattern, but build it as a
  fixed overlay above `.rail`, so "everything else is hidden" is literally
  true rather than only the Hub being hidden.
- **`in_progress` already exists**, with a play control on every task row.
  Focusing a task should set it, so the state is honest and renders everywhere
  it already renders. Completing clears it (`toggleTask()` already does this).
- **Boolean flags are a worn path.** `priority` is a column plus
  `toggleTaskPriority()` plus `saveOrRollback()`. `dreaded` is the same shape,
  roughly fifteen lines.
- **Week already has a pending strip** — `.pending-area` and
  `renderPendingChipsInto()`, currently holding unassigned tasks. That is the
  natural home for parked thoughts.
- **Capture writes to the `notes` table** via `saveCapture()`, with `day`,
  `event_title`, and `project`.
- **`priorityFirst()`** is the existing ordering helper that floats flagged
  tasks up. Dreaded ordering has to be reconciled with it rather than added
  beside it.

## Three findings worth remembering

1. **The Mac app does not need to catch up.** It is a pywebview wrapper
   pointing at `https://jessieebie.github.io/taskwell/` (`APP_URL` in
   `Taskwell mac app/taskwell_webview.py`). Everything built in the web app
   appears there on next launch. The only real gaps are OS-level: notifications
   and keeping the screen awake.

2. **Taskwell is not actually a PWA.** There is no manifest and no service
   worker; "Add to Dock" works off the `apple-touch-icon`. It will not work
   offline, and iOS may suspend the page mid-session. So the timer must be
   built on wall-clock timestamps, never on counting ticks, or locking the
   iPad and returning will corrupt it. Adding a real manifest and service
   worker is separate work, if wanted.

3. **"Done today" needs a new column.** Tasks have `completed` but no
   `completed_at`. The Today tab's existing "completed" section is not the same
   thing — it shows tasks *assigned to today* that are done, so it misses
   something finished today from another day's pile and wrongly includes
   something assigned today but finished last week. Add `completed_at`, set it
   in `toggleTask()`. Existing completed tasks have no timestamp and simply
   will not appear, which is a clean start rather than a wrong history.

## Plan for 1 and 2

### Focus mode

A fixed overlay, entered from a task row in Hub, a chip in Week, or the task
detail modal.

- List name small and quiet; task title large; its notes underneath if any.
- Timer counts **down from 10 minutes**. At zero it does not alarm or scold —
  it says something like "Ten minutes done. Stop here, or keep going," and
  quietly counts up. That keeps the promise rather than starting a new demand.
- Three controls only: **Park a thought**, **Done**, **Exit**.
- Session start stored in `localStorage` as a timestamp, so a reload or a
  resumed Mac app window picks up where it was.
- Request Screen Wake Lock so the iPad does not dim mid-session. Progressive
  enhancement; harmless where unsupported.
- Entering focus sets `in_progress`. Exiting leaves it set (the task was in
  fact started). Completing clears it, as it already does.

### Parking lot

- One real `<textarea>` — not a contenteditable div, which is unreliable with
  Scribble — one **Park it** button, no dropdowns and no decisions.
- Writes through the existing capture path, flashes "Parked — you'll see it in
  Week," and returns to the task after about a second.
- No modal to dismiss. One tap in, one tap out.

## Open decisions, still to be made

### 1. Where a parked thought lands

The spec asks for parked thoughts to go to **Capture** and to show up in
**Week**. Notes never appear in Week today — only tasks do. Three ways to make
the promise true:

- **Capture plus a Parked strip in Week** (recommended). Writes a note, and
  adds a small "Parked" row to Week's existing pending area. Stray thoughts
  stay thoughts until they are decided to be tasks, so they do not swell the
  task list that is already too long. Needs one new column on `notes`.
- **Make it an unassigned task.** Appears in Week's pending chips with no new
  structure at all, but every half-thought becomes another thing competing for
  attention, which is the problem being solved.
- **Capture only.** Simplest; the focus message says "you'll see it in
  Capture" instead. Does not match the spec.

### 2. Whether "done today" and `completed_at` land in this round

Recommended: yes, now. It is one column, it pairs naturally with finishing a
focus session, and rolling it into this migration avoids a second trip to
Supabase later.

## SQL, once the decisions above are made

For 1 and 2 with the recommended answers:

```sql
alter table public.notes
  add column if not exists parked boolean default false;

alter table public.tasks
  add column if not exists completed_at timestamptz;
```

Later, for 3 and 4:

```sql
alter table public.tasks
  add column if not exists dreaded boolean default false,
  add column if not exists first_step text,
  add column if not exists picked_for date;
```

## Sketches for 3 and 4 (not designed in detail yet)

**Dreaded and shrink it.** `dreaded boolean` plus `first_step text` on tasks.
Be honest about "suggests": there is no model call in the app, so a suggestion
means a small built-in library of generic openers, offered as a few tappable
options alongside a free-text box — not intelligence. Floating dreaded tasks up
the Hub has to be reconciled with `priorityFirst()` rather than fighting it.

**Pick three.** Ride on `week_assigned` rather than inventing a parallel idea
of "today," with a `picked_for date` column set to today when chosen, so it
expires on its own. Cap gently: a fourth pick offers to swap one out rather
than refusing.

## Housekeeping

- `taskwell.html` is the source. `index.html` is a served copy — always
  `cp taskwell.html index.html` before every commit.
- `APP_VERSION` must be bumped to the real current date on every push.
- `tests/regression.html` is deliberately gitignored. Run it before every
  push: `python3 -m http.server 8934`, then open
  `http://localhost:8934/tests/regression.html`. 86 tests as of this pause.
