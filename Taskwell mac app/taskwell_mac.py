#!/usr/bin/env python3
"""
Taskwell — Mac App
Synced with Supabase. Hub · Week · Day · Inbox
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import urllib.request
import urllib.error
import os
from datetime import date, timedelta, datetime
import calendar as cal_module

try:
    from EventKit import EKEventStore, EKEntityTypeEvent
    from Foundation import NSDate
    from AppKit import NSEvent
    NSEventMaskScrollWheel = 1 << 22
    HAS_EVENTKIT = True
except ImportError:
    HAS_EVENTKIT = False
    NSEvent = None
    NSEventMaskScrollWheel = 0

# ── Config ──
SUPABASE_URL = "https://vblmnfjbtoeeytmzgbaf.supabase.co"
SUPABASE_KEY = "sb_publishable_s9VIKwo6dnfrcpM-5KjEMg_NEPGzhFU"
INBOX_FILE   = os.path.expanduser("~/.taskwell_inbox.json")
CAL_PREFS_FILE = os.path.expanduser("~/.taskwell_cal_prefs.json")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

# ── Colors (earthy palette) ──
CREAM      = "#F5F0E8"
CREAM_DARK = "#EDE6D6"
PAPER      = "#FAF7F2"
INK        = "#2E2118"
INK_SOFT   = "#6B5744"
INK_FAINT  = "#B8A898"
RUST       = "#B85C38"

# Palette-derived accent sets
BROWN      = "#A67B5B"   # warm brown  — work rail
ROSE       = "#C4A4A0"   # dusty rose  — work accent
ROSE_PALE  = "#EDE0DB"   # blush       — work pale
SAGE       = "#9CAF9A"   # sage green  — home accent/rail
SAGE_PALE  = "#D8E5D6"   # light sage  — home pale
KHAKI      = "#C4B99A"   # warm khaki  — all rail/accent
KHAKI_PALE = "#EDE7DA"   # light khaki — all pale

FONT_SERIF       = ("Georgia", 13)
FONT_SERIF_TITLE = ("Georgia", 22)
FONT_SERIF_SM    = ("Georgia", 11)
FONT_SANS        = ("Helvetica Neue", 12)
FONT_SANS_SM     = ("Helvetica Neue", 10)
FONT_SANS_BOLD   = ("Helvetica Neue", 12, "bold")
FONT_SANS_BOLD_SM = ("Helvetica Neue", 10, "bold")

WORK_SECTIONS = ["Service", "Teaching", "Research", "Misc"]

# ── API ──
def api(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        content = r.read()
        if not content:
            return None
        return json.loads(content)

def api_bg(method, path, body=None, callback=None):
    def run():
        try:
            result = api(method, path, body)
            if callback:
                callback(result, None)
        except Exception as e:
            if callback:
                callback(None, e)
    threading.Thread(target=run, daemon=True).start()

# ── Local persistence ──
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

# ── Date helpers ──
def parse_date_input(val):
    """MM/DD/YY or MM/DD/YYYY → ISO string, or None."""
    val = val.strip()
    if not val:
        return None
    for fmt in ('%m/%d/%y', '%m/%d/%Y'):
        try:
            return datetime.strptime(val, fmt).date().isoformat()
        except:
            continue
    return None

def fmt_display(iso):
    """2025-07-15 → 07/15/25"""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%m/%d/%y")
    except:
        return iso

def fmt_for_input(iso):
    return fmt_display(iso)

def make_date_var(trace_write=None):
    """StringVar that auto-inserts slashes as the user types MM/DD/YY."""
    var = tk.StringVar()
    _busy = [False]
    def _on_change(*_):
        if _busy[0]:
            return
        raw = var.get()
        digits = ''.join(c for c in raw if c.isdigit())
        out = digits
        if len(digits) > 2:
            out = digits[:2] + '/' + digits[2:]
        if len(digits) > 4:
            out = out[:5] + '/' + out[5:]
        out = out[:8]
        if out != raw:
            _busy[0] = True
            var.set(out)
            _busy[0] = False
        if trace_write:
            trace_write()
    var.trace_add('write', _on_change)
    return var


# ════════════════════════════════════════
# MAIN APP
# ════════════════════════════════════════
class TaskwellApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Taskwell")
        self.root.geometry("1000x720")
        self.root.minsize(800, 560)
        self.root.configure(bg=CREAM_DARK)

        # Data
        self.lists = []
        self.tasks = []
        self.inbox_items = load_json(INBOX_FILE, [])

        # UI state
        self.current_context = "work"   # 'work' | 'home' | 'all'
        self.active_section  = "hub"
        self.active_week_list = "all"
        self.week_offset     = 0        # 0 = current week
        self.section_collapsed = {s: False for s in WORK_SECTIONS}
        self.section_collapsed["__home"] = False
        self.list_collapsed  = {}
        self.editing_task_id = None
        self.selected_day    = date.today().isoformat()
        self.mini_month      = date.today().replace(day=1)

        # Drag state
        self._drag_task_id  = None
        self._drag_window   = None
        self._day_columns   = {}

        self._build_ui()
        self.status_var.set("Connecting…")
        self._load_data()
        self._init_calendar()

    # ── Accent colors based on context ──
    @property
    def accent(self):
        if self.current_context == "home": return SAGE
        if self.current_context == "all":  return KHAKI
        return ROSE

    @property
    def accent_pale(self):
        if self.current_context == "home": return SAGE_PALE
        if self.current_context == "all":  return KHAKI_PALE
        return ROSE_PALE

    @property
    def rail_bg(self):
        if self.current_context == "home": return SAGE
        if self.current_context == "all":  return KHAKI
        return BROWN

    # ── Scroll helpers ──
    def _init_global_scroll(self):
        """Intercept trackpad/scroll events via NSEvent local monitor (bypasses tkinter event quirks)."""
        self._active_scroll = None  # (canvas, orient) for the currently visible tab
        self._ns_monitor = None
        self._scroll_carry = 0.0   # sub-unit accumulator for smooth scroll

        def _dispatch(units, canvas, orient):
            try:
                if orient == 'y':
                    canvas.yview_scroll(units, "units")
                else:
                    canvas.xview_scroll(units, "units")
            except Exception:
                pass

        if NSEvent:
            def _ns_scroll(ns_event):
                if not self._active_scroll:
                    return ns_event
                canvas, orient = self._active_scroll
                dy = float(ns_event.scrollingDeltaY() if orient == 'y'
                           else ns_event.scrollingDeltaX())
                # Accumulate until we have at least 1 unit to scroll
                self._scroll_carry += dy
                units = int(self._scroll_carry / 8)  # 8px per unit feels natural
                if units:
                    self._scroll_carry -= units * 8
                    self.root.after(0, _dispatch, -units, canvas, orient)
                return ns_event

            self._ns_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                NSEventMaskScrollWheel, _ns_scroll)

        # Tkinter binding as fallback for non-NSEvent environments
        def _tk_scroll(e):
            if not self._active_scroll:
                return
            canvas, orient = self._active_scroll
            raw = e.delta
            if raw == 0:
                return
            amt = -int(raw / 120) if abs(raw) >= 120 else int(-raw)
            if amt == 0:
                amt = 1 if raw < 0 else -1
            _dispatch(amt, canvas, orient)

        self.root.bind_all('<MouseWheel>', _tk_scroll)

    def _register_scroll(self, canvas, orient='y'):
        pass  # kept for call-site compatibility; routing is now done via _active_scroll

    # ── Calendar (EventKit) ──
    def _init_calendar(self):
        self.cal_store = None
        self.cal_events_all = {}  # date_str -> [event_dict, ...] (unfiltered)
        saved = load_json(CAL_PREFS_FILE, {})
        raw = saved.get("selected")
        # None or empty list from old code = no real selection → show all (None sentinel)
        self.cal_selected = set(raw) if raw else None
        if not HAS_EVENTKIT:
            return
        self.cal_store = EKEventStore.alloc().init()

        def on_auth(granted, error):
            if granted:
                self.root.after(0, self._refresh_cal_events)

        try:
            self.cal_store.requestFullAccessToEventsWithCompletion_(on_auth)
        except AttributeError:
            self.cal_store.requestAccessToEntityType_completion_(EKEntityTypeEvent, on_auth)

    def _nsdate_to_dt(self, nsdate):
        return datetime.fromtimestamp(float(nsdate.timeIntervalSince1970()))

    def _date_to_nsdate(self, d):
        ts = datetime(d.year, d.month, d.day).timestamp()
        return NSDate.dateWithTimeIntervalSince1970_(ts)

    def _cal_color(self, ek_cal):
        try:
            c = ek_cal.color()
            r = int(c.redComponent() * 255)
            g = int(c.greenComponent() * 255)
            b = int(c.blueComponent() * 255)
            # darken very light colors so white text stays readable
            if r + g + b > 600:
                r, g, b = int(r * 0.7), int(g * 0.7), int(b * 0.7)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return "#5B8DB8"

    def _refresh_cal_events(self):
        if not self.cal_store:
            return
        today = date.today()
        fetch_start = today - timedelta(days=7)
        fetch_end   = today + timedelta(days=60)
        start_ns = self._date_to_nsdate(fetch_start)
        end_ns   = self._date_to_nsdate(fetch_end + timedelta(days=1))

        def fetch():
            result = {}
            try:
                pred = self.cal_store.predicateForEventsWithStartDate_endDate_calendars_(
                    start_ns, end_ns, None)
                events = self.cal_store.eventsMatchingPredicate_(pred) or []
                for ev in events:
                    try:
                        cal_id   = str(ev.calendar().calendarIdentifier())
                        start_dt = self._nsdate_to_dt(ev.startDate())
                        end_dt   = self._nsdate_to_dt(ev.endDate())
                        all_day  = bool(ev.isAllDay())
                        title    = str(ev.title() or "(No title)")
                        cal_name = str(ev.calendar().title() or "")
                        color    = self._cal_color(ev.calendar())
                        entry = {"title": title, "start": start_dt, "end": end_dt,
                                 "all_day": all_day, "calendar": cal_name,
                                 "color": color, "cal_id": cal_id}
                        result.setdefault(start_dt.date().isoformat(), []).append(entry)
                    except Exception:
                        pass
            except Exception:
                pass
            self.root.after(0, self._on_cal_loaded, result)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_cal_loaded(self, result):
        # Store ALL events unfiltered; get_cal_events() applies the selection at render time
        self.cal_events_all = result
        if self.active_section == "week":
            self._render_week()
        elif self.active_section == "day":
            self._render_agenda()

    def get_cal_events(self, date_key):
        """Return calendar events for date_key, filtered by cal_selected.
        Empty cal_selected means no preference saved yet — show all calendars."""
        evs = self.cal_events_all.get(date_key, [])
        # cal_selected is None only before any preference is ever saved;
        # an empty set means the user explicitly unchecked everything.
        if self.cal_selected is None:
            return evs
        if len(self.cal_selected) == 0:
            return []
        return [e for e in evs if e["cal_id"] in self.cal_selected]

    def _cal_chooser(self):
        if not self.cal_store:
            messagebox.showinfo("Calendars", "Calendar access not available.", parent=self.root)
            return
        cals = list(self.cal_store.calendarsForEntityType_(EKEntityTypeEvent) or [])
        if not cals:
            messagebox.showinfo("Calendars", "No calendars found.", parent=self.root)
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Choose Calendars")
        dlg.geometry("320x400")
        dlg.resizable(False, False)
        dlg.configure(bg=PAPER)
        dlg.transient(self.root)
        dlg.grab_set()

        tk.Label(dlg, text="Show calendars:", font=FONT_SANS_BOLD, bg=PAPER, fg=INK,
                 anchor="w").pack(fill=tk.X, padx=20, pady=(16, 8))

        vars_map = {}
        scroll_f = tk.Frame(dlg, bg=PAPER)
        scroll_f.pack(fill=tk.BOTH, expand=True, padx=20)

        for cal in sorted(cals, key=lambda c: str(c.title())):
            cal_id = str(cal.calendarIdentifier())
            title  = str(cal.title() or "")
            color  = self._cal_color(cal)
            checked = self.cal_selected is None or cal_id in self.cal_selected
            var = tk.BooleanVar(value=checked)
            vars_map[cal_id] = var
            row = tk.Frame(scroll_f, bg=PAPER)
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text="●", fg=color, bg=PAPER, font=FONT_SANS_SM).pack(side=tk.LEFT)
            tk.Checkbutton(row, text=title, variable=var, bg=PAPER, fg=INK,
                           font=FONT_SANS_SM, activebackground=PAPER,
                           selectcolor=CREAM_DARK).pack(side=tk.LEFT, padx=6)

        def save():
            selected = {cal_id for cal_id, var in vars_map.items() if var.get()}
            self.cal_selected = selected
            save_json(CAL_PREFS_FILE, {"selected": list(selected)})
            dlg.destroy()
            self._render_week()
            self._render_agenda()

        def cancel():
            dlg.destroy()

        dlg.protocol("WM_DELETE_WINDOW", cancel)

        btn_row = tk.Frame(dlg, bg=PAPER)
        btn_row.pack(pady=16, padx=20, fill=tk.X)
        tk.Button(btn_row, text="Cancel", bg=CREAM, fg=INK, font=FONT_SANS,
                  relief=tk.RAISED, padx=14, pady=6, cursor="hand2",
                  activebackground=CREAM_DARK, command=cancel).pack(side=tk.LEFT)
        tk.Button(btn_row, text="Save", bg=self.accent, fg="white", font=FONT_SANS_BOLD,
                  relief=tk.RAISED, padx=20, pady=6, cursor="hand2",
                  activebackground=self.accent, command=save).pack(side=tk.RIGHT)

    # ── List context helpers ──
    def get_list_ctx(self, lst):
        return lst.get("context") or "work"

    def get_visible_lists(self):
        if self.current_context == "all":
            return self.lists
        return [l for l in self.lists if self.get_list_ctx(l) == self.current_context]

    # ════════════════════════
    # UI BUILD
    # ════════════════════════
    def _build_ui(self):
        self.sidebar = tk.Frame(self.root, bg=self.rail_bg, width=76)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.main_frame = tk.Frame(self.root, bg=PAPER)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var,
                 bg=CREAM_DARK, fg=INK_FAINT, font=FONT_SANS_SM,
                 anchor="e", padx=10).pack(side=tk.BOTTOM, fill=tk.X)

        self.sections = {}
        self._init_global_scroll()
        self._build_sidebar()
        self._build_hub()
        self._build_week()
        self._build_day()
        self._build_inbox()
        self._show_section("hub")
        # Hub is the opening tab; set active scroll now that canvas exists
        self._active_scroll = (self.hub_canvas, 'y')

    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()

        bg = self.rail_bg

        # App mark — clicking shows 'all'
        mark_bg = CREAM
        mark = tk.Label(self.sidebar, text="✓", bg=mark_bg, fg=self.accent,
                        font=("Georgia", 14, "bold"), width=2, pady=6, cursor="hand2",
                        relief=tk.RAISED if self.current_context == "all" else tk.FLAT)
        mark.pack(pady=(16, 8), padx=10)
        mark.bind("<Button-1>", lambda e: self._set_context("all"))

        # Work / Home context switcher
        for ctx, icon, label in [("work", "⊛", "Work"), ("home", "⌂", "Home")]:
            is_active = self.current_context == ctx
            f = tk.Frame(self.sidebar, bg=CREAM if is_active else bg, cursor="hand2")
            f.pack(pady=2, padx=8, fill=tk.X)
            f.bind("<Button-1>", lambda e, c=ctx: self._set_context(c))
            for text, font in [(icon, ("Helvetica Neue", 16)), (label, FONT_SANS_SM)]:
                lbl = tk.Label(f, text=text, bg=CREAM if is_active else bg,
                               fg=INK, font=font, pady=2)
                lbl.pack()
                lbl.bind("<Button-1>", lambda e, c=ctx: self._set_context(c))

        tk.Frame(self.sidebar, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=12, pady=8)

        # Tab buttons
        self.tab_buttons = {}
        tabs = [
            ("hub",   "⊞",  "Hub"),
            ("week",  "◫",  "Week"),
            ("day",   "◷",  "Day"),
            ("inbox", "✉",  "Inbox"),
        ]
        for key, icon, label in tabs:
            is_active = self.active_section == key
            f = tk.Frame(self.sidebar, bg=ROSE_PALE if is_active else bg, cursor="hand2")
            f.pack(pady=3, padx=8, fill=tk.X)
            f.bind("<Button-1>", lambda e, k=key: self._show_section(k))
            for text, font in [(icon, ("Helvetica Neue", 18)), (label, FONT_SANS_SM)]:
                lbl = tk.Label(f, text=text, bg=ROSE_PALE if is_active else bg,
                               fg=INK, font=font, pady=3)
                lbl.pack()
                lbl.bind("<Button-1>", lambda e, k=key: self._show_section(k))
            self.tab_buttons[key] = f

    def _show_section(self, name):
        self.active_section = name
        for key, frame in self.sections.items():
            frame.pack_forget()
        if name in self.sections:
            self.sections[name].pack(fill=tk.BOTH, expand=True)
        self._build_sidebar()  # rebuild to update active highlights
        # Route trackpad scroll to the active tab's canvas
        scroll_map = {
            'hub':   (self.hub_canvas,    'y'),
            'week':  (self._week_canvas,  'x'),
            'day':   (self.day_canvas,    'y'),
            'inbox': (self.inbox_canvas,  'y'),
        }
        self._active_scroll = scroll_map.get(name)
        if name == "week":
            self._render_week()
        elif name == "hub":
            self._render_hub()
        elif name == "day":
            self._render_mini_cal()
            self._render_agenda()
        elif name == "inbox":
            self._render_inbox()

    def _set_context(self, ctx):
        self.current_context = ctx
        self.sidebar.configure(bg=self.rail_bg)
        self._build_sidebar()
        sec = self.active_section
        if sec == "hub":
            self._render_hub()
        elif sec == "week":
            self._render_week()
        elif sec == "day":
            self._render_mini_cal()
            self._render_agenda()
        elif sec == "inbox":
            self._render_inbox()

    # ════════════════════════
    # HUB
    # ════════════════════════
    def _build_hub(self):
        frame = tk.Frame(self.main_frame, bg=PAPER)
        self.sections["hub"] = frame

        hdr = tk.Frame(frame, bg=PAPER)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 0))
        self.hub_title = tk.Label(hdr, text="Hub", font=FONT_SERIF_TITLE, bg=PAPER, fg=INK)
        self.hub_title.pack(side=tk.LEFT)
        self.hub_subtitle = tk.Label(hdr, text="", font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT)
        self.hub_subtitle.pack(side=tk.LEFT, padx=(10, 0), pady=(6, 0))
        tk.Button(hdr, text="+ New List", bg=CREAM, fg=INK, font=FONT_SANS_BOLD,
                  relief=tk.RAISED, padx=12, pady=4, cursor="hand2",
                  activebackground=CREAM_DARK, command=self._new_list_dialog).pack(side=tk.RIGHT)

        ctrl = tk.Frame(frame, bg=PAPER)
        ctrl.pack(fill=tk.X, padx=20, pady=(6, 0))
        for text, cmd in [("Collapse all", self._collapse_all), ("Expand all", self._expand_all)]:
            tk.Button(ctrl, text=text, bg=CREAM_DARK, fg=INK, font=FONT_SANS_SM,
                      relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                      activebackground=CREAM_DARK, command=cmd).pack(side=tk.LEFT, padx=(0, 4))

        tk.Frame(frame, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=20, pady=(8, 0))

        outer = tk.Frame(frame, bg=PAPER)
        outer.pack(fill=tk.BOTH, expand=True)

        self.hub_canvas = tk.Canvas(outer, bg=PAPER, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.hub_canvas.yview)
        self.hub_scroll_frame = tk.Frame(self.hub_canvas, bg=PAPER)
        self.hub_scroll_frame.bind("<Configure>",
            lambda e: self.hub_canvas.configure(scrollregion=self.hub_canvas.bbox("all")))
        self.hub_canvas.create_window((0, 0), window=self.hub_scroll_frame, anchor="nw")
        self.hub_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hub_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._register_scroll(self.hub_canvas, 'y')

    def _collapse_all(self):
        for s in WORK_SECTIONS:
            self.section_collapsed[s] = True
        self.section_collapsed["__home"] = True
        self._render_hub()

    def _expand_all(self):
        for s in WORK_SECTIONS:
            self.section_collapsed[s] = False
        self.section_collapsed["__home"] = False
        for lst in self.lists:
            self.list_collapsed[lst["id"]] = False
        self._render_hub()

    def _render_hub(self):
        for w in self.hub_scroll_frame.winfo_children():
            w.destroy()

        visible = self.get_visible_lists()
        titles = {"work": "Work Hub", "home": "Home", "all": "Hub"}
        self.hub_title.configure(text=titles.get(self.current_context, "Hub"))
        self.hub_subtitle.configure(
            text="Your task lists" if not visible else f"{len(visible)} list{'s' if len(visible) != 1 else ''}")

        if self.current_context == "all":
            # Banner so "all" mode is visually distinct
            banner = tk.Frame(self.hub_scroll_frame, bg=KHAKI_PALE, padx=16, pady=6)
            banner.pack(fill=tk.X, padx=20, pady=(6, 12))
            tk.Label(banner, text="Showing all contexts — Home + Work",
                     font=FONT_SANS_SM, bg=KHAKI_PALE, fg=INK).pack(anchor="w")

            home_lists = [l for l in self.lists if self.get_list_ctx(l) == "home"]
            self._render_section_block(self.hub_scroll_frame, "Home", "__home", home_lists)
            for sec in WORK_SECTIONS:
                sec_lists = [l for l in self.lists
                             if l.get("section", "Misc") == sec and self.get_list_ctx(l) == "work"]
                if sec_lists:
                    self._render_section_block(self.hub_scroll_frame, sec, sec, sec_lists)

        elif self.current_context == "home":
            if not visible:
                tk.Label(self.hub_scroll_frame, text="No home lists yet. Create one!",
                         font=("Georgia", 12, "italic"), bg=PAPER, fg=INK_FAINT
                         ).pack(anchor="w", padx=20, pady=16)
            else:
                grid = tk.Frame(self.hub_scroll_frame, bg=PAPER)
                grid.pack(fill=tk.X, padx=20, pady=(8, 0))
                grid.columnconfigure(0, weight=1, uniform="col")
                grid.columnconfigure(1, weight=1, uniform="col")
                for i, lst in enumerate(visible):
                    r, c = divmod(i, 2)
                    cell = tk.Frame(grid, bg=CREAM, highlightthickness=1,
                                    highlightbackground=CREAM_DARK)
                    cell.grid(row=r, column=c, sticky="nsew",
                              padx=(0, 6 if c == 0 else 0), pady=(0, 6))
                    self._render_list_block(cell, lst)
        else:
            for sec in WORK_SECTIONS:
                sec_lists = [l for l in self.lists
                             if l.get("section", "Misc") == sec and self.get_list_ctx(l) == "work"]
                if self.current_context == "work" or sec_lists:
                    self._render_section_block(self.hub_scroll_frame, sec, sec, sec_lists)

        self.hub_canvas.configure(scrollregion=self.hub_canvas.bbox("all"))

    def _render_section_block(self, parent, display_name, key, sec_lists):
        collapsed = self.section_collapsed.get(key, False)

        sec_frame = tk.Frame(parent, bg=PAPER)
        sec_frame.pack(fill=tk.X, padx=20, pady=(18, 0))

        # Section header: accent-colored left bar + all-caps label
        hdr = tk.Frame(sec_frame, bg=PAPER, cursor="hand2")
        hdr.pack(fill=tk.X, pady=(0, 8))
        tk.Frame(hdr, bg=self.accent, width=3).pack(side=tk.LEFT, fill=tk.Y)
        lbl = tk.Label(hdr, text=display_name,
                       font=("Helvetica Neue", 15, "bold"), bg=PAPER, fg=INK,
                       anchor="w", padx=10, pady=4, cursor="hand2")
        lbl.pack(side=tk.LEFT)
        arrow_lbl = tk.Label(hdr, text="▾" if not collapsed else "▸",
                             font=FONT_SANS_SM, bg=PAPER, fg=INK_FAINT, cursor="hand2")
        arrow_lbl.pack(side=tk.LEFT)

        def toggle(k=key):
            self.section_collapsed[k] = not self.section_collapsed.get(k, False)
            self._render_hub()

        for w in (hdr, lbl, arrow_lbl):
            w.bind("<Button-1>", lambda e: toggle())

        if collapsed:
            return

        if not sec_lists:
            tk.Label(sec_frame, text="No lists yet — add one above",
                     font=("Georgia", 11, "italic"), bg=PAPER, fg=INK_FAINT
                     ).pack(anchor="w", padx=14, pady=4)
            return

        # 2-column grid
        grid = tk.Frame(sec_frame, bg=PAPER)
        grid.pack(fill=tk.X)
        grid.columnconfigure(0, weight=1, uniform="col")
        grid.columnconfigure(1, weight=1, uniform="col")

        for i, lst in enumerate(sec_lists):
            r, c = divmod(i, 2)
            cell = tk.Frame(grid, bg=CREAM, bd=0,
                            highlightthickness=1, highlightbackground=CREAM_DARK)
            cell.grid(row=r, column=c, sticky="nsew", padx=(0 if c else 0, 6 if c == 0 else 0),
                      pady=(0, 6))
            self._render_list_block(cell, lst)

    def _render_list_block(self, parent, lst):
        list_id = lst["id"]
        collapsed = self.list_collapsed.get(list_id, False)
        list_tasks = [t for t in self.tasks if t["list_id"] == list_id]
        open_tasks  = [t for t in list_tasks if not t.get("completed")]
        done_tasks  = [t for t in list_tasks if t.get("completed")]
        lctx = self.get_list_ctx(lst)
        bg = parent.cget("bg")

        block = tk.Frame(parent, bg=bg)
        block.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        lhdr = tk.Frame(block, bg=bg, cursor="hand2")
        lhdr.pack(fill=tk.X, padx=10, pady=(8, 4))

        # Context dot in all-mode
        if self.current_context == "all":
            dot_color = SAGE if lctx == "home" else ROSE
            tk.Label(lhdr, text="●", bg=bg, fg=dot_color, font=FONT_SANS_SM
                     ).pack(side=tk.LEFT, padx=(0, 4))

        name_lbl = tk.Label(lhdr, text=lst["name"], font=("Helvetica Neue", 13, "bold", "underline"),
                            bg=bg, fg=INK, anchor="w", cursor="hand2")
        name_lbl.pack(side=tk.LEFT)

        if open_tasks:
            tk.Label(lhdr, text=str(len(open_tasks)),
                     font=FONT_SANS_SM, bg=self.accent_pale, fg=INK,
                     padx=5, pady=1).pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(lhdr, text="✕", bg=bg, fg=INK_FAINT,
                  font=FONT_SANS_SM, relief=tk.FLAT, bd=0, cursor="hand2",
                  activeforeground=RUST,
                  command=lambda lid=list_id, ln=lst["name"]: self._delete_list(lid, ln)
                  ).pack(side=tk.RIGHT)

        arrow_lbl = tk.Label(lhdr, text="▾" if not collapsed else "▸",
                             font=FONT_SANS_SM, bg=bg, fg=INK_FAINT, cursor="hand2")
        arrow_lbl.pack(side=tk.RIGHT, padx=(0, 4))

        def toggle_lst(lid=list_id):
            self.list_collapsed[lid] = not self.list_collapsed.get(lid, False)
            self._render_hub()

        for w in [lhdr, name_lbl, arrow_lbl]:
            w.bind("<Button-1>", lambda e: toggle_lst())

        if collapsed:
            return

        if not open_tasks:
            tk.Label(block, text="No tasks yet",
                     font=("Georgia", 11, "italic"), bg=bg, fg=INK_FAINT
                     ).pack(anchor="w", padx=10, pady=(0, 4))
        else:
            for t in open_tasks:
                self._make_task_row(block, t)

        if done_tasks:
            done_hdr = tk.Frame(block, bg=bg)
            done_hdr.pack(fill=tk.X, padx=10, pady=(4, 0))
            tk.Label(done_hdr, text=f"{len(done_tasks)} completed",
                     font=FONT_SANS_SM, bg=bg, fg=INK_FAINT).pack(side=tk.LEFT)
            tk.Button(done_hdr, text="Clear", bg=bg, fg=INK_FAINT,
                      font=FONT_SANS_SM, relief=tk.FLAT, bd=0, padx=0, pady=2, cursor="hand2",
                      activeforeground=RUST,
                      command=lambda lid=list_id: self._clear_completed(lid)).pack(side=tk.RIGHT)
            for t in done_tasks:
                self._make_task_row(block, t, done=True)

        # Task input row — at the bottom
        input_row = tk.Frame(block, bg=bg)
        input_row.pack(fill=tk.X, pady=(6, 8), padx=10)

        task_entry = tk.Entry(input_row, font=FONT_SANS_SM, bg=PAPER, fg=INK,
                              relief=tk.FLAT, bd=0, insertbackground=INK)
        task_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, ipadx=6)
        task_entry.configure(highlightthickness=1, highlightbackground=CREAM_DARK,
                             highlightcolor=self.accent)

        due_var = make_date_var()
        due_entry = tk.Entry(input_row, textvariable=due_var, font=FONT_SANS_SM, bg=PAPER, fg=INK,
                             relief=tk.FLAT, bd=0, insertbackground=INK, width=8)
        due_entry.pack(side=tk.LEFT, padx=(4, 0), ipady=4, ipadx=4)
        due_entry.configure(highlightthickness=1, highlightbackground=CREAM_DARK,
                            highlightcolor=self.accent)

        def add(lid=list_id, te=task_entry, dv=due_var):
            self._add_task(lid, te, dv)

        task_entry.bind("<Return>", lambda e: add())
        tk.Button(input_row, text="+", bg=self.accent, fg="white", font=FONT_SANS_BOLD,
                  relief=tk.FLAT, padx=8, pady=3, cursor="hand2",
                  activebackground=self.accent, command=add).pack(side=tk.LEFT, padx=(4, 0))

        tk.Frame(block, bg=bg, height=8).pack(fill=tk.X)  # bottom padding

    def _make_task_row(self, parent, task, done=False):
        bg = parent.cget("bg")
        row = tk.Frame(parent, bg=bg)
        row.pack(fill=tk.X, padx=10, pady=1)

        check_var = tk.BooleanVar(value=done)
        tk.Checkbutton(row, variable=check_var, bg=bg, activebackground=bg,
                       fg=self.accent, selectcolor=self.accent, relief=tk.FLAT, bd=0, cursor="hand2",
                       command=lambda tid=task["id"], v=check_var: self._toggle_task(tid, v)
                       ).pack(side=tk.LEFT)

        fg   = INK_FAINT if done else INK
        font = ("Georgia", 11, "overstrike") if done else ("Georgia", 11)
        tk.Label(row, text=task["title"], font=font, bg=bg, fg=fg,
                 anchor="w").pack(side=tk.LEFT, padx=(2, 0))

        # Due date badge
        due = task.get("due_date")
        if due:
            try:
                due_date = date.fromisoformat(due)
                today    = date.today()
                diff     = (due_date - today).days
                if diff < 0:
                    bg2, fg2, txt = RUST, PAPER, f"Overdue"
                elif diff == 0:
                    bg2, fg2, txt = self.accent_pale, INK, "Today"
                elif diff == 1:
                    bg2, fg2, txt = CREAM_DARK, INK, "Tmrw"
                else:
                    bg2, fg2, txt = CREAM_DARK, INK_SOFT, due_date.strftime("%-m/%-d")
                tk.Label(row, text=txt, bg=bg2, fg=fg2, font=FONT_SANS_SM,
                         padx=5, pady=1).pack(side=tk.LEFT, padx=(6, 0))
            except:
                pass

        tk.Button(row, text="×", bg=bg, fg=INK_FAINT,
                  font=FONT_SANS, relief=tk.FLAT, bd=0, cursor="hand2",
                  activeforeground=RUST,
                  command=lambda tid=task["id"]: self._delete_task(tid)
                  ).pack(side=tk.RIGHT)
        tk.Button(row, text="✎", bg=bg, fg=INK_FAINT, font=FONT_SANS_SM,
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  activeforeground=self.accent,
                  command=lambda tid=task["id"]: self._open_edit_task(tid)
                  ).pack(side=tk.RIGHT, padx=(0, 2))

    def _add_task(self, list_id, entry_widget, due_var):
        title = entry_widget.get().strip()
        if not title:
            return
        due_date = parse_date_input(due_var.get())
        entry_widget.delete(0, tk.END)
        due_var.set("")
        body = {"list_id": list_id, "title": title, "completed": False, "due_date": due_date}
        api_bg("POST", "tasks", body,
               callback=lambda r, e: self.root.after(0, self._on_task_added, r, e))

    def _on_task_added(self, result, error):
        if error or not result:
            self.status_var.set(f"Error: {error}")
            return
        self.tasks.append(result[0])
        self._render_hub()
        if self.active_section == "week":
            self._render_week()
        self.status_var.set("Task added")

    def _toggle_task(self, task_id, var):
        done = var.get()
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if task:
            task["completed"] = done
        self._render_hub()
        if self.active_section == "week":
            self._render_week()
        if self.active_section == "day":
            self._render_agenda()
        api_bg("PATCH", f"tasks?id=eq.{task_id}", {"completed": done})

    def _delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self._render_hub()
        if self.active_section == "week":
            self._render_week()
        api_bg("DELETE", f"tasks?id=eq.{task_id}")

    def _delete_list(self, list_id, name):
        if not messagebox.askyesno("Delete List",
                                   f'Delete "{name}" and all its tasks?\nThis cannot be undone.',
                                   parent=self.root):
            return
        self.tasks = [t for t in self.tasks if t["list_id"] != list_id]
        self.lists = [l for l in self.lists if l["id"] != list_id]
        self._render_hub()
        if self.active_section == "week":
            self._render_week()
        api_bg("DELETE", f"tasks?list_id=eq.{list_id}")
        api_bg("DELETE", f"lists?id=eq.{list_id}")

    def _clear_completed(self, list_id):
        ids = [t["id"] for t in self.tasks if t["list_id"] == list_id and t.get("completed")]
        self.tasks = [t for t in self.tasks if not (t["list_id"] == list_id and t.get("completed"))]
        self._render_hub()
        if self.active_section == "week":
            self._render_week()
        for tid in ids:
            api_bg("DELETE", f"tasks?id=eq.{tid}")

    def _open_edit_task(self, task_id):
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return
        self.editing_task_id = task_id

        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Task")
        dialog.geometry("340x220")
        dialog.configure(bg=PAPER)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Task", font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT
                 ).pack(pady=(20, 4), padx=20, anchor="w")
        title_entry = tk.Entry(dialog, font=FONT_SERIF, bg=CREAM, fg=INK,
                               relief=tk.FLAT, bd=0, insertbackground=INK)
        title_entry.pack(fill=tk.X, padx=20, ipady=7, ipadx=8)
        title_entry.configure(highlightthickness=1, highlightbackground=CREAM_DARK,
                              highlightcolor=self.accent)
        title_entry.insert(0, task["title"])
        title_entry.focus()

        tk.Label(dialog, text="Due date (MM/DD/YY)", font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT
                 ).pack(pady=(12, 4), padx=20, anchor="w")
        due_var = make_date_var()
        due_entry = tk.Entry(dialog, textvariable=due_var, font=FONT_SANS, bg=CREAM, fg=INK,
                             relief=tk.FLAT, bd=0, insertbackground=INK, width=14)
        due_entry.pack(anchor="w", padx=20, ipady=5, ipadx=8)
        due_entry.configure(highlightthickness=1, highlightbackground=CREAM_DARK,
                            highlightcolor=self.accent)
        if task.get("due_date"):
            due_var.set(fmt_for_input(task["due_date"]))

        def save():
            title = title_entry.get().strip()
            if not title:
                return
            due_date = parse_date_input(due_var.get())
            dialog.destroy()
            task["title"]    = title
            task["due_date"] = due_date
            self._render_hub()
            if self.active_section == "week":
                self._render_week()
            if self.active_section == "day":
                self._render_agenda()
            api_bg("PATCH", f"tasks?id=eq.{task_id}", {"title": title, "due_date": due_date})

        title_entry.bind("<Return>", lambda e: save())

        btn_row = tk.Frame(dialog, bg=PAPER)
        btn_row.pack(pady=14)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  bg=CREAM, fg=INK, relief=tk.RAISED, padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="Save", command=save,
                  bg=CREAM, fg=INK, relief=tk.RAISED, padx=14, pady=6).pack(side=tk.LEFT, padx=6)

    def _new_list_dialog(self):
        is_home = self.current_context == "home"
        dialog = tk.Toplevel(self.root)
        dialog.title("New List")
        dialog.geometry("300x200" if is_home else "300x240")
        dialog.configure(bg=PAPER)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="List name", font=FONT_SERIF, bg=PAPER, fg=INK
                 ).pack(pady=(20, 6), padx=20, anchor="w")
        name_entry = tk.Entry(dialog, font=FONT_SERIF, bg=CREAM, fg=INK,
                              relief=tk.FLAT, bd=0, insertbackground=INK)
        name_entry.pack(fill=tk.X, padx=20, ipady=7, ipadx=8)
        name_entry.configure(highlightthickness=1, highlightbackground=CREAM_DARK,
                             highlightcolor=self.accent)
        name_entry.focus()

        section_var = tk.StringVar(value="Misc")
        if not is_home:
            tk.Label(dialog, text="Section", font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT
                     ).pack(pady=(12, 4), padx=20, anchor="w")
            ttk.Combobox(dialog, values=WORK_SECTIONS, textvariable=section_var,
                         state="readonly", font=FONT_SANS).pack(fill=tk.X, padx=20)

        def confirm():
            name = name_entry.get().strip()
            if not name:
                return
            section = "Misc" if is_home else section_var.get()
            context = "home" if is_home else "work"
            dialog.destroy()
            api_bg("POST", "lists", {"name": name, "section": section, "context": context},
                   callback=lambda r, e: self.root.after(0, self._on_list_created, r, e))

        name_entry.bind("<Return>", lambda e: confirm())
        btn_row = tk.Frame(dialog, bg=PAPER)
        btn_row.pack(pady=14)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  bg=CREAM, fg=INK, relief=tk.RAISED, padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="Create", command=confirm,
                  bg=CREAM, fg=INK, relief=tk.RAISED, padx=14, pady=6).pack(side=tk.LEFT, padx=6)

    def _on_list_created(self, result, error):
        if error or not result:
            self.status_var.set(f"Error: {error}")
            return
        lst = result[0]
        self.lists.append(lst)
        self._render_hub()
        self.status_var.set(f'List "{lst["name"]}" created')

    # ════════════════════════
    # WEEK
    # ════════════════════════
    def _build_week(self):
        frame = tk.Frame(self.main_frame, bg=PAPER)
        self.sections["week"] = frame

        hdr = tk.Frame(frame, bg=PAPER)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 0))
        tk.Label(hdr, text="Week", font=FONT_SERIF_TITLE, bg=PAPER, fg=INK).pack(side=tk.LEFT)
        self.week_subtitle = tk.Label(hdr, text="", font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT)
        self.week_subtitle.pack(side=tk.LEFT, padx=(10, 0), pady=(6, 0))

        # Navigation row
        nav = tk.Frame(frame, bg=PAPER)
        nav.pack(fill=tk.X, padx=20, pady=(8, 0))
        tk.Button(nav, text="‹ Prev", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                  relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=lambda: self._week_nav(-1)).pack(side=tk.LEFT)
        self.today_btn = tk.Button(nav, text="Today", bg=self.accent, fg=PAPER, font=FONT_SANS_SM,
                                   relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                                   command=lambda: self._week_nav(0))
        # Today button packed conditionally in _render_week
        tk.Button(nav, text="Next ›", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                  relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=lambda: self._week_nav(1)).pack(side=tk.LEFT, padx=(6, 0))

        # List filter tabs
        self.week_filter_frame = tk.Frame(frame, bg=PAPER)
        self.week_filter_frame.pack(fill=tk.X, padx=20, pady=(8, 0))

        # Pending chips
        pending_outer = tk.Frame(frame, bg=CREAM)
        pending_outer.pack(fill=tk.X, padx=20, pady=(10, 0))
        tk.Label(pending_outer, text="UNASSIGNED — drag to a day",
                 font=FONT_SANS_SM, bg=CREAM, fg=INK_FAINT).pack(anchor="w", padx=10, pady=(8, 4))
        self.pending_frame = tk.Frame(pending_outer, bg=CREAM)
        self.pending_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        tk.Frame(frame, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=20, pady=(8, 0))

        # Scrollable week grid
        self._week_outer = tk.Frame(frame, bg=PAPER)
        self._week_outer.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 0))
        self._week_xscroll = ttk.Scrollbar(frame, orient="horizontal")
        self._week_xscroll.pack(fill=tk.X, padx=20, side=tk.BOTTOM)
        self._week_canvas = tk.Canvas(self._week_outer, bg=PAPER, highlightthickness=0,
                                      xscrollcommand=self._week_xscroll.set)
        self._week_canvas.pack(fill=tk.BOTH, expand=True)
        self._week_xscroll.config(command=self._week_canvas.xview)
        self._week_inner = tk.Frame(self._week_canvas, bg=PAPER)
        self._week_inner_id = self._week_canvas.create_window(
            (0, 0), window=self._week_inner, anchor="nw")
        self._week_inner.bind("<Configure>",
            lambda e: self._week_canvas.configure(scrollregion=self._week_canvas.bbox("all")))
        self._week_canvas.bind("<Configure>",
            lambda e: self._week_canvas.itemconfig(self._week_inner_id, height=e.height))
        # Trackpad horizontal scroll
        self._register_scroll(self._week_canvas, 'x')

    def _week_nav(self, delta):
        if delta == 0:
            self.week_offset = 0
        else:
            self.week_offset += delta
        self._render_week()

    def _get_week_days(self):
        today = date.today()
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        sunday += timedelta(weeks=self.week_offset)
        return [sunday + timedelta(days=i) for i in range(7)]

    def _render_week(self):
        days = self._get_week_days()
        today = date.today()

        self.week_subtitle.configure(
            text=f"{days[0].strftime('%b %-d')} – {days[6].strftime('%b %-d')}")

        # Show/hide Today button
        if self.week_offset != 0:
            self.today_btn.configure(bg=self.accent)
            self.today_btn.pack(side=tk.LEFT, padx=(6, 0))
        else:
            self.today_btn.pack_forget()

        # List filter tabs
        for w in self.week_filter_frame.winfo_children():
            w.destroy()
        visible = self.get_visible_lists()
        for key, label in [("all", "All")] + [(l["id"], l["name"]) for l in visible]:
            is_active = self.active_week_list == key
            tk.Button(self.week_filter_frame, text=label,
                      bg=self.accent_pale if is_active else CREAM, fg=INK,
                      font=FONT_SANS_SM, relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                      activebackground=CREAM_DARK,
                      command=lambda k=key: self._set_week_list(k)
                      ).pack(side=tk.LEFT, padx=(0, 4))

        # Pending chips
        for w in self.pending_frame.winfo_children():
            w.destroy()
        vis_ids = {l["id"] for l in visible}
        unassigned = [t for t in self.tasks
                      if not t.get("week_assigned") and not t.get("completed")
                      and t["list_id"] in vis_ids
                      and (self.active_week_list == "all" or t["list_id"] == self.active_week_list)]
        if not unassigned:
            tk.Label(self.pending_frame, text="All tasks assigned ✓",
                     font=FONT_SANS_SM, bg=CREAM, fg=INK_FAINT).pack(anchor="w")
        else:
            row_f = tk.Frame(self.pending_frame, bg=CREAM)
            row_f.pack(fill=tk.X)
            for t in unassigned:
                label_text = t["title"]
                if t.get("due_date"):
                    label_text += f"  ·  {fmt_display(t['due_date'])}"
                chip = tk.Label(row_f, text=label_text, bg=CREAM_DARK, fg=INK,
                                font=FONT_SANS_SM, relief=tk.RAISED, padx=8, pady=4, cursor="fleur")
                chip.pack(side=tk.LEFT, padx=(0, 6), pady=2)
                self._bind_drag(chip, t["id"])

        # Day columns
        for w in self._week_inner.winfo_children():
            w.destroy()
        self._day_columns = {}
        day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        COL_W = 168

        for i, day in enumerate(days):
            is_today = day == today
            key = day.isoformat()
            card_bg = self.accent_pale if is_today else CREAM

            # Tasks assigned to this day OR tasks with due_date on this day (not already assigned elsewhere)
            day_tasks = [t for t in self.tasks
                         if t["list_id"] in vis_ids
                         and (self.active_week_list == "all" or t["list_id"] == self.active_week_list)
                         and (t.get("week_assigned") == key
                              or (not t.get("week_assigned") and t.get("due_date") == key))]

            col = tk.Frame(self._week_inner, bg=card_bg, padx=6, pady=6, width=COL_W)
            col.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 4))
            col.pack_propagate(False)
            self._day_columns[key] = col

            hdr_bg = self.accent if is_today else CREAM_DARK
            hdr = tk.Frame(col, bg=hdr_bg)
            hdr.pack(fill=tk.X, pady=(0, 6))
            tk.Label(hdr, text=day_names[i], font=FONT_SANS_BOLD, bg=hdr_bg,
                     fg=INK, padx=6, pady=4).pack(side=tk.LEFT)
            tk.Label(hdr, text=day.strftime("%-d"), font=FONT_SANS_SM, bg=hdr_bg,
                     fg=INK_SOFT, padx=4).pack(side=tk.RIGHT)

            if not day_tasks:
                lbl = tk.Label(col, text="Drop here", font=("Georgia", 11, "italic"),
                               bg=card_bg, fg=INK_FAINT)
                lbl.pack(pady=10)
                self._bind_drop(lbl, key)
            else:
                for t in day_tasks:
                    lst = next((l for l in self.lists if l["id"] == t["list_id"]), None)
                    done = t.get("completed", False)
                    t_card = tk.Frame(col, bg=PAPER, padx=6, pady=4)
                    t_card.pack(fill=tk.X, pady=2)

                    title_font = ("Georgia", 11, "overstrike") if done else ("Georgia", 11)
                    title_fg   = INK_FAINT if done else INK
                    tk.Label(t_card, text=t["title"], font=title_font, bg=PAPER, fg=title_fg,
                             wraplength=130, anchor="w", justify=tk.LEFT).pack(anchor="w")

                    meta_row = tk.Frame(t_card, bg=PAPER)
                    meta_row.pack(fill=tk.X, anchor="w")
                    if lst:
                        tk.Label(meta_row, text=lst["name"], font=FONT_SANS_SM, bg=PAPER,
                                 fg=INK_FAINT).pack(side=tk.LEFT)
                    if t.get("due_date"):
                        tk.Label(meta_row, text=fmt_display(t["due_date"]), font=FONT_SANS_SM,
                                 bg=PAPER, fg=INK_FAINT).pack(side=tk.RIGHT)

                    def unassign(tid=t["id"]):
                        task = next((x for x in self.tasks if x["id"] == tid), None)
                        if task:
                            task["week_assigned"] = None
                            task["due_date"]      = None
                        self._render_week()
                        self._render_hub()
                        api_bg("PATCH", f"tasks?id=eq.{tid}", {"week_assigned": None, "due_date": None})

                    tk.Button(t_card, text="Remove", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                              relief=tk.RAISED, padx=4, pady=1, cursor="hand2",
                              command=unassign).pack(anchor="e", pady=(2, 0))

                    # Make card draggable — skip Button children so Remove still works
                    self._bind_drag(t_card, t["id"])
                    for child in t_card.winfo_children():
                        if not isinstance(child, tk.Button):
                            self._bind_drag(child, t["id"])

            # Calendar events for this day
            cal_day = sorted(self.get_cal_events(key), key=lambda e: (e["all_day"], e["start"]))
            if cal_day:
                tk.Frame(col, bg=CREAM_DARK, height=1).pack(fill=tk.X, pady=(4, 2))
            for ev in cal_day:
                ev_f = tk.Frame(col, bg=ev["color"], padx=5, pady=3)
                ev_f.pack(fill=tk.X, pady=1)
                tk.Label(ev_f, text=ev["title"], font=FONT_SANS_BOLD_SM,
                         bg=ev["color"], fg="white", wraplength=130,
                         anchor="w", justify=tk.LEFT).pack(anchor="w")
                if not ev["all_day"]:
                    t_str = ev["start"].strftime("%-I:%M") + "–" + ev["end"].strftime("%-I:%M %p")
                    tk.Label(ev_f, text=t_str, font=FONT_SANS_SM,
                             bg=ev["color"], fg="white").pack(anchor="w")

            # Whole column is a drop target
            self._bind_drop(col, key)
            for child in col.winfo_children():
                self._bind_drop(child, key)

        self._week_inner.update_idletasks()
        self._week_canvas.configure(scrollregion=self._week_canvas.bbox("all"))

    def _bind_drag(self, widget, task_id):
        def on_start(e):
            self._drag_task_id = task_id
            if self._drag_window:
                try: self._drag_window.destroy()
                except: pass
            task = next((t for t in self.tasks if t["id"] == task_id), None)
            if not task:
                return
            self._drag_window = tk.Toplevel(self.root)
            self._drag_window.overrideredirect(True)
            self._drag_window.attributes("-alpha", 0.85)
            tk.Label(self._drag_window, text=task["title"], bg=self.accent, fg=INK,
                     font=FONT_SANS_SM, padx=10, pady=6, relief=tk.RAISED).pack()
            self._drag_window.geometry(f"+{e.x_root+12}+{e.y_root+12}")

        def on_drag(e):
            if self._drag_window:
                self._drag_window.geometry(f"+{e.x_root+12}+{e.y_root+12}")

        def on_release(e):
            if self._drag_window:
                try: self._drag_window.destroy()
                except: pass
                self._drag_window = None
            if not self._drag_task_id:
                return
            x, y = e.x_root, e.y_root
            for day_key, col in self._day_columns.items():
                try:
                    cx, cy = col.winfo_rootx(), col.winfo_rooty()
                    if cx <= x <= cx + col.winfo_width() and cy <= y <= cy + col.winfo_height():
                        self._assign_to_day(self._drag_task_id, day_key)
                        break
                except:
                    pass
            self._drag_task_id = None

        widget.bind("<ButtonPress-1>", on_start)
        widget.bind("<B1-Motion>", on_drag)
        widget.bind("<ButtonRelease-1>", on_release)

    def _bind_drop(self, widget, day_key):
        pass  # Drop is handled by coordinate check in on_release

    def _assign_to_day(self, task_id, day_key):
        task = next((t for t in self.tasks if t["id"] == task_id), None)
        if not task:
            return
        task["week_assigned"] = day_key
        task["due_date"]      = day_key
        self._render_week()
        self._render_hub()
        api_bg("PATCH", f"tasks?id=eq.{task_id}", {"week_assigned": day_key, "due_date": day_key})
        self.status_var.set(f"Assigned to {day_key}")

    def _set_week_list(self, key):
        self.active_week_list = key
        self._render_week()

    # ════════════════════════
    # DAY VIEW
    # ════════════════════════
    def _build_day(self):
        frame = tk.Frame(self.main_frame, bg=PAPER)
        self.sections["day"] = frame

        hdr = tk.Frame(frame, bg=PAPER)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 0))
        tk.Label(hdr, text="Day", font=FONT_SERIF_TITLE, bg=PAPER, fg=INK).pack(side=tk.LEFT)
        self.day_subtitle = tk.Label(hdr, text="", font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT)
        self.day_subtitle.pack(side=tk.LEFT, padx=(10, 0), pady=(6, 0))
        tk.Button(hdr, text="Calendars ▾", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                  relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=self._cal_chooser).pack(side=tk.RIGHT)

        # Split view: agenda (left) + mini-cal (right)
        split = tk.Frame(frame, bg=PAPER)
        split.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        # Agenda
        agenda_outer = tk.Frame(split, bg=PAPER)
        agenda_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.day_canvas = tk.Canvas(agenda_outer, bg=PAPER, highlightthickness=0)
        day_scroll = ttk.Scrollbar(agenda_outer, orient="vertical", command=self.day_canvas.yview)
        self.day_scroll_frame = tk.Frame(self.day_canvas, bg=PAPER)
        self.day_scroll_frame.bind("<Configure>",
            lambda e: self.day_canvas.configure(scrollregion=self.day_canvas.bbox("all")))
        self.day_canvas.create_window((0, 0), window=self.day_scroll_frame, anchor="nw")
        self.day_canvas.configure(yscrollcommand=day_scroll.set)
        day_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.day_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._register_scroll(self.day_canvas, 'y')

        # Sidebar: mini-cal
        sidebar = tk.Frame(split, bg=CREAM, width=200)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Mini-cal header
        cal_nav = tk.Frame(sidebar, bg=CREAM)
        cal_nav.pack(fill=tk.X, padx=10, pady=(12, 6))
        tk.Button(cal_nav, text="‹", bg=CREAM, fg=INK, font=("Helvetica Neue", 14),
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  command=self._mini_cal_prev).pack(side=tk.LEFT)
        self.mini_cal_title = tk.Label(cal_nav, text="", font=FONT_SANS_BOLD,
                                       bg=CREAM, fg=INK)
        self.mini_cal_title.pack(side=tk.LEFT, expand=True)
        tk.Button(cal_nav, text="›", bg=CREAM, fg=INK, font=("Helvetica Neue", 14),
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  command=self._mini_cal_next).pack(side=tk.RIGHT)

        # Mini-cal grid (rebuilt in _render_mini_cal)
        self.mini_cal_grid_frame = tk.Frame(sidebar, bg=CREAM)
        self.mini_cal_grid_frame.pack(fill=tk.X, padx=8)

        # Calendar connect note removed — EventKit handles it natively

    def _render_mini_cal(self):
        for w in self.mini_cal_grid_frame.winfo_children():
            w.destroy()

        today    = date.today()
        year     = self.mini_month.year
        month    = self.mini_month.month

        self.mini_cal_title.configure(
            text=self.mini_month.strftime("%B %Y"))

        # Day-of-week headers
        for i, d in enumerate(["Su","Mo","Tu","We","Th","Fr","Sa"]):
            tk.Label(self.mini_cal_grid_frame, text=d, font=FONT_SANS_BOLD_SM,
                     bg=CREAM, fg=INK_FAINT, width=3).grid(row=0, column=i, pady=(0, 2))

        first_day = date(year, month, 1)
        start_col = first_day.weekday() + 1  # Monday=0 → col 1; Sunday → col 0
        start_col = first_day.isoweekday() % 7  # Sunday=0

        # Previous month padding
        for col in range(start_col):
            d = first_day - timedelta(days=start_col - col)
            tk.Label(self.mini_cal_grid_frame, text=str(d.day), font=FONT_SANS_SM,
                     bg=CREAM, fg=INK_FAINT, width=3).grid(row=1, column=col)

        days_in_month = cal_module.monthrange(year, month)[1]
        task_dates = {t.get("week_assigned") or t.get("due_date") for t in self.tasks
                      if not t.get("completed")}

        row, col = 1, start_col
        for d in range(1, days_in_month + 1):
            dt  = date(year, month, d)
            key = dt.isoformat()
            is_today    = dt == today
            is_selected = key == self.selected_day
            has_tasks   = key in task_dates

            if is_selected:
                bg, fg = self.accent, PAPER
            elif is_today:
                bg, fg = self.accent_pale, INK
            else:
                bg, fg = CREAM, INK

            lbl = tk.Label(self.mini_cal_grid_frame, text=str(d), font=FONT_SANS_SM,
                           bg=bg, fg=fg, width=3, cursor="hand2",
                           relief=tk.FLAT, bd=1)
            lbl.grid(row=row, column=col, padx=1, pady=1)
            lbl.bind("<Button-1>", lambda e, k=key: self._select_day(k))

            if has_tasks and not is_selected:
                lbl.configure(text=f"{d}·")

            col += 1
            if col == 7:
                col = 0
                row += 1

    def _mini_cal_prev(self):
        m = self.mini_month
        if m.month == 1:
            self.mini_month = date(m.year - 1, 12, 1)
        else:
            self.mini_month = date(m.year, m.month - 1, 1)
        self._render_mini_cal()

    def _mini_cal_next(self):
        m = self.mini_month
        if m.month == 12:
            self.mini_month = date(m.year + 1, 1, 1)
        else:
            self.mini_month = date(m.year, m.month + 1, 1)
        self._render_mini_cal()

    def _select_day(self, key):
        self.selected_day = key
        self._render_mini_cal()
        self._render_agenda()

    def _render_agenda(self):
        for w in self.day_scroll_frame.winfo_children():
            w.destroy()

        try:
            sd = date.fromisoformat(self.selected_day)
        except:
            sd = date.today()

        self.day_subtitle.configure(
            text=sd.strftime("%A, %B %-d, %Y"))

        tk.Label(self.day_scroll_frame,
                 text=sd.strftime("%A, %B %-d"),
                 font=("Georgia", 18), bg=PAPER, fg=INK
                 ).pack(anchor="w", padx=20, pady=(12, 8))

        vis_ids = {l["id"] for l in self.get_visible_lists()}
        day_tasks = [t for t in self.tasks
                     if t["list_id"] in vis_ids and not t.get("completed")
                     and (t.get("week_assigned") == self.selected_day
                          or t.get("due_date") == self.selected_day)]

        if day_tasks:
            tk.Label(self.day_scroll_frame, text="TASKS",
                     font=FONT_SANS_BOLD_SM, bg=PAPER, fg=INK_FAINT
                     ).pack(anchor="w", padx=20, pady=(0, 4))
            for t in day_tasks:
                lst = next((l for l in self.lists if l["id"] == t["list_id"]), None)
                row = tk.Frame(self.day_scroll_frame, bg=CREAM, bd=0)
                row.pack(fill=tk.X, padx=20, pady=2)

                check_var = tk.BooleanVar(value=False)
                tk.Checkbutton(row, variable=check_var, bg=CREAM, activebackground=CREAM,
                               fg=self.accent, selectcolor=self.accent, relief=tk.FLAT, bd=0,
                               command=lambda tid=t["id"], v=check_var: self._toggle_task(tid, v)
                               ).pack(side=tk.LEFT, padx=(8, 0), pady=6)
                info = tk.Frame(row, bg=CREAM)
                info.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=6)
                tk.Label(info, text=t["title"], font=FONT_SERIF_SM, bg=CREAM, fg=INK,
                         anchor="w").pack(anchor="w")
                if lst:
                    tk.Label(info, text=lst["name"], font=FONT_SANS_SM, bg=CREAM,
                             fg=INK_FAINT, anchor="w").pack(anchor="w")
        elif not self.get_cal_events(self.selected_day):
            tk.Label(self.day_scroll_frame,
                     text="Nothing scheduled for this day.",
                     font=("Georgia", 12, "italic"), bg=PAPER, fg=INK_FAINT
                     ).pack(anchor="w", padx=20, pady=16)

        # Calendar events
        cal_day = sorted(self.get_cal_events(self.selected_day),
                         key=lambda e: (not e["all_day"], e["start"]))
        if cal_day:
            tk.Label(self.day_scroll_frame, text="CALENDAR",
                     font=FONT_SANS_BOLD_SM, bg=PAPER, fg=INK_FAINT
                     ).pack(anchor="w", padx=20, pady=(12, 4))
            for ev in cal_day:
                row = tk.Frame(self.day_scroll_frame, bg=ev["color"])
                row.pack(fill=tk.X, padx=20, pady=2)
                if ev["all_day"]:
                    time_str = "All day"
                else:
                    time_str = (ev["start"].strftime("%-I:%M") +
                                "–" + ev["end"].strftime("%-I:%M %p"))
                tk.Label(row, text=time_str, font=FONT_SANS_SM, bg=ev["color"],
                         fg="white", padx=8, pady=4, width=14, anchor="w").pack(side=tk.LEFT)
                tk.Label(row, text=ev["title"], font=FONT_SERIF_SM, bg=ev["color"],
                         fg="white", padx=4, pady=4, anchor="w"
                         ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif HAS_EVENTKIT and not self.cal_store:
            tk.Label(self.day_scroll_frame,
                     text="Calendar access not granted. Check System Settings → Privacy → Calendars.",
                     font=FONT_SANS_SM, bg=PAPER, fg=INK_FAINT, wraplength=380, justify=tk.LEFT
                     ).pack(anchor="w", padx=20, pady=(12, 8))

        self.day_canvas.configure(scrollregion=self.day_canvas.bbox("all"))

    def _cal_google_info(self):
        messagebox.showinfo(
            "Connect Google Calendar",
            "To sync Google Calendar:\n\n"
            "1. Go to https://console.cloud.google.com\n"
            "2. Create a project → enable Google Calendar API\n"
            "3. Create an OAuth 2.0 Client ID\n"
            "4. Add your redirect URI\n"
            "5. Paste the Client ID into the GOOGLE_CLIENT_ID constant\n"
            "   in the Taskwell.html file.\n\n"
            "Calendar sync is available in the web version.",
            parent=self.root
        )

    def _cal_outlook_info(self):
        messagebox.showinfo(
            "Connect Outlook Calendar",
            "To sync Outlook:\n\n"
            "1. Go to https://portal.azure.com → App registrations\n"
            "2. Register the app, add a redirect URI\n"
            "3. Grant Calendar.Read permission\n"
            "4. Paste the Application (client) ID into the MS_CLIENT_ID\n"
            "   constant in the Taskwell.html file.\n\n"
            "Calendar sync is available in the web version.",
            parent=self.root
        )

    # ════════════════════════
    # INBOX
    # ════════════════════════
    def _build_inbox(self):
        frame = tk.Frame(self.main_frame, bg=PAPER)
        self.sections["inbox"] = frame

        hdr = tk.Frame(frame, bg=PAPER)
        hdr.pack(fill=tk.X, padx=20, pady=(18, 0))
        tk.Label(hdr, text="Inbox", font=FONT_SERIF_TITLE, bg=PAPER, fg=INK).pack(side=tk.LEFT)
        tk.Label(hdr, text="Tasks to assign to a list",
                 font=FONT_SANS_SM, bg=PAPER, fg=INK_SOFT).pack(side=tk.LEFT, padx=(10, 0), pady=(6, 0))

        input_row = tk.Frame(frame, bg=PAPER)
        input_row.pack(fill=tk.X, padx=20, pady=(14, 0))
        self.inbox_entry = tk.Entry(input_row, font=FONT_SERIF, bg=CREAM, fg=INK,
                                    relief=tk.FLAT, bd=0, insertbackground=INK)
        self.inbox_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=7, ipadx=10)
        self.inbox_entry.configure(highlightthickness=1, highlightbackground=CREAM_DARK,
                                   highlightcolor=self.accent)
        self.inbox_entry.bind("<Return>", lambda e: self._add_inbox_item())
        tk.Button(input_row, text="Add", bg=CREAM, fg=INK, font=FONT_SANS_BOLD,
                  relief=tk.RAISED, padx=14, pady=6, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=self._add_inbox_item).pack(side=tk.LEFT, padx=(8, 0))

        tk.Frame(frame, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=20, pady=(12, 0))

        outer = tk.Frame(frame, bg=PAPER)
        outer.pack(fill=tk.BOTH, expand=True)
        self.inbox_canvas = tk.Canvas(outer, bg=PAPER, highlightthickness=0)
        inbox_scroll = ttk.Scrollbar(outer, orient="vertical", command=self.inbox_canvas.yview)
        self.inbox_scroll_frame = tk.Frame(self.inbox_canvas, bg=PAPER)
        self.inbox_scroll_frame.bind("<Configure>",
            lambda e: self.inbox_canvas.configure(scrollregion=self.inbox_canvas.bbox("all")))
        self.inbox_canvas.create_window((0, 0), window=self.inbox_scroll_frame, anchor="nw")
        self.inbox_canvas.configure(yscrollcommand=inbox_scroll.set)
        inbox_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.inbox_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._register_scroll(self.inbox_canvas, 'y')

    def _render_inbox(self):
        for w in self.inbox_scroll_frame.winfo_children():
            w.destroy()

        if not self.inbox_items:
            tk.Label(self.inbox_scroll_frame,
                     text="No items. Add tasks you need to assign to a list.",
                     font=("Georgia", 12, "italic"), bg=PAPER, fg=INK_FAINT
                     ).pack(anchor="w", padx=20, pady=16)
        else:
            for i, item in enumerate(self.inbox_items):
                done = item.get("done", False)
                row = tk.Frame(self.inbox_scroll_frame, bg=PAPER)
                row.pack(fill=tk.X, padx=20)
                tk.Frame(row, bg=CREAM_DARK, height=1).pack(fill=tk.X)
                content = tk.Frame(row, bg=PAPER)
                content.pack(fill=tk.X, pady=6)

                check_var = tk.BooleanVar(value=done)
                tk.Checkbutton(content, variable=check_var, bg=PAPER, activebackground=PAPER,
                               fg=self.accent, selectcolor=self.accent, relief=tk.FLAT, bd=0,
                               cursor="hand2",
                               command=lambda idx=i, v=check_var: self._toggle_inbox_item(idx, v)
                               ).pack(side=tk.LEFT)

                font = ("Georgia", 12, "overstrike") if done else ("Georgia", 12)
                fg   = INK_FAINT if done else INK
                tk.Label(content, text=item["text"], font=font, bg=PAPER, fg=fg,
                         anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

                tk.Button(content, text="Assign →", bg=CREAM, fg=INK,
                          font=FONT_SANS_SM, relief=tk.FLAT, padx=8, pady=3, cursor="hand2",
                          command=lambda idx=i: self._assign_inbox_item(idx)
                          ).pack(side=tk.RIGHT, padx=(6, 0))
                tk.Button(content, text="×", bg=PAPER, fg=INK_FAINT,
                          font=("Helvetica Neue", 14), relief=tk.FLAT, bd=0, cursor="hand2",
                          activeforeground=RUST,
                          command=lambda idx=i: self._delete_inbox_item(idx)).pack(side=tk.RIGHT)

        self.inbox_canvas.configure(scrollregion=self.inbox_canvas.bbox("all"))

    def _add_inbox_item(self):
        val = self.inbox_entry.get().strip()
        if not val:
            return
        self.inbox_entry.delete(0, tk.END)
        self.inbox_items.insert(0, {"text": val, "done": False})
        save_json(INBOX_FILE, self.inbox_items)
        self._render_inbox()

    def _toggle_inbox_item(self, idx, var):
        if idx < len(self.inbox_items):
            self.inbox_items[idx]["done"] = var.get()
            save_json(INBOX_FILE, self.inbox_items)

    def _delete_inbox_item(self, idx):
        if idx < len(self.inbox_items):
            self.inbox_items.pop(idx)
            save_json(INBOX_FILE, self.inbox_items)
            self._render_inbox()

    def _assign_inbox_item(self, item_idx):
        if not self.lists:
            messagebox.showinfo("No Lists", "Create a list in Hub first.", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Assign to List")
        dialog.geometry("300x180")
        dialog.configure(bg=PAPER)
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        tk.Label(dialog, text="Assign to which list?", font=FONT_SERIF,
                 bg=PAPER, fg=INK).pack(pady=(20, 10))
        visible = self.get_visible_lists() or self.lists
        combo = ttk.Combobox(dialog, values=[l["name"] for l in visible],
                              state="readonly", font=FONT_SANS)
        combo.current(0)
        combo.pack(padx=20, fill=tk.X)

        def confirm():
            chosen = visible[combo.current()]
            item   = self.inbox_items[item_idx]
            dialog.destroy()
            self.inbox_items[item_idx]["done"] = True
            save_json(INBOX_FILE, self.inbox_items)
            self._render_inbox()
            api_bg("POST", "tasks",
                   {"list_id": chosen["id"], "title": item["text"], "completed": False},
                   callback=lambda r, e: self.root.after(0, self._on_task_added, r, e))

        btn_row = tk.Frame(dialog, bg=PAPER)
        btn_row.pack(pady=14)
        tk.Button(btn_row, text="Cancel", command=dialog.destroy,
                  bg=CREAM, fg=INK, relief=tk.RAISED, padx=14, pady=6).pack(side=tk.LEFT, padx=6)
        tk.Button(btn_row, text="Assign", command=confirm,
                  bg=CREAM, fg=INK, relief=tk.RAISED, padx=14, pady=6).pack(side=tk.LEFT, padx=6)

    # ════════════════════════
    # DATA LOAD
    # ════════════════════════
    def _load_data(self):
        def fetch():
            try:
                lists = api("GET", "lists?order=created_at.asc")
                tasks = api("GET", "tasks?order=created_at.asc")
                self.root.after(0, self._on_data_loaded, lists, tasks)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Connection error: {e}"))
        threading.Thread(target=fetch, daemon=True).start()

    def _on_data_loaded(self, lists, tasks):
        self.lists = lists or []
        self.tasks = tasks or []
        self._render_hub()
        if self.active_section == "day":
            self._render_mini_cal()
            self._render_agenda()
        self.status_var.set(f"Loaded {len(self.lists)} lists, {len(self.tasks)} tasks")


def main():
    root = tk.Tk()
    root.title("Taskwell")
    try:
        root.createcommand('tk::mac::ReopenApplication', root.deiconify)
    except:
        pass
    TaskwellApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
