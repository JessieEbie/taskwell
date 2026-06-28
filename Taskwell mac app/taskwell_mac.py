#!/usr/bin/env python3
"""
Taskwell — Mac App
Synced with Supabase. Hub · Week · Day · Inbox
"""
BUILD_TIMESTAMP = "2026-06-27"

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import json
import urllib.request
import urllib.error
import urllib.parse
import os
import hashlib
import base64
import secrets
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import date, timedelta, datetime
import calendar as cal_module

try:
    from AppKit import NSEvent
    NSEventMaskScrollWheel = 1 << 22
    HAS_APPKIT = True
except ImportError:
    HAS_APPKIT = False
    NSEvent = None
    NSEventMaskScrollWheel = 0

# ── Local persistence (defined early, needed by auth) ──
def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)

# ── Config ──
SUPABASE_URL   = "https://vblmnfjbtoeeytmzgbaf.supabase.co"
SUPABASE_KEY   = "sb_publishable_s9VIKwo6dnfrcpM-5KjEMg_NEPGzhFU"
ALLOWED_EMAIL  = "jessieebie@gmail.com"
INBOX_FILE      = os.path.expanduser("~/.taskwell_inbox.json")
AUTH_FILE       = os.path.expanduser("~/.taskwell_auth.json")
ICS_FEEDS_FILE  = os.path.expanduser("~/.taskwell_ics_feeds.json")
OAUTH_PORT     = 54321
OAUTH_REDIRECT = f"http://localhost:{OAUTH_PORT}"

# ── Auth state ──
_auth = load_json(AUTH_FILE, {}) if os.path.exists(AUTH_FILE) else {}

def _get_user_id():
    return (_auth.get("user_id")
            or _auth.get("user", {}).get("id"))

def _auth_headers():
    token = _auth.get("access_token", SUPABASE_KEY)
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

def _save_auth(data):
    global _auth
    _auth = data
    save_json(AUTH_FILE, data)

def _clear_auth():
    global _auth
    _auth = {}
    try: os.remove(AUTH_FILE)
    except: pass

def _decode_jwt_email(token):
    try:
        payload = token.split('.')[1]
        payload += '=' * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded.get('email', ''), decoded.get('sub', '')
    except:
        return '', ''

def _pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b'=').decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b'=').decode()
    return verifier, challenge

def _exchange_code(code, verifier):
    body = json.dumps({"auth_code": code, "code_verifier": verifier}).encode()
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce",
        data=body,
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def _refresh_token():
    if not _auth.get("refresh_token"): return False
    try:
        body = json.dumps({"refresh_token": _auth["refresh_token"]}).encode()
        req = urllib.request.Request(
            f"{SUPABASE_URL}/auth/v1/token?grant_type=refresh_token",
            data=body,
            headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            _save_auth(data)
            return True
    except:
        return False

def is_logged_in():
    return bool(_auth.get("access_token"))

def login_with_google(on_success, on_error):
    result_holder = [None]

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            token = (params.get('access_token', [None])[0])
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            if token:
                self.wfile.write(b'<html><body><h2>Signed in! You can close this tab.</h2></body></html>')
                result_holder[0] = {
                    'access_token': token,
                    'refresh_token': params.get('refresh_token', [None])[0],
                    'user_id': params.get('user_id', [None])[0],
                }
            else:
                self.wfile.write(b'<html><body><h2>Sign-in failed. Please try again.</h2></body></html>')
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    def _run():
        try:
            server = HTTPServer(('localhost', OAUTH_PORT), _Handler)
            web_url = f"https://jessieebie.github.io/taskwell/?mac_callback=1"
            webbrowser.open(web_url)
            server.serve_forever()
            data = result_holder[0]
            if not data:
                on_error("Sign-in cancelled or failed.")
                return
            email, uid = _decode_jwt_email(data.get("access_token", ""))
            if email != ALLOWED_EMAIL:
                on_error(f"Access denied for {email}.")
                return
            if uid and not data.get('user_id'):
                data['user_id'] = uid
            _save_auth(data)
            on_success()
        except Exception as e:
            on_error(str(e))

    threading.Thread(target=_run, daemon=True).start()

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
def api(method, path, body=None, extra_headers=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    data = json.dumps(body).encode() if body else None
    def make_req():
        h = {**_auth_headers(), **(extra_headers or {})}
        return urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(make_req(), timeout=10) as r:
            content = r.read()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as e:
        if e.code == 401 and _refresh_token():
            with urllib.request.urlopen(make_req(), timeout=10) as r:
                content = r.read()
                return json.loads(content) if content else None
        raise

def load_cal_feeds():
    try:
        rows = api('GET', f'user_settings?user_id=eq.{_get_user_id()}&select=cal_feeds')
        return (rows[0]['cal_feeds'] if rows else None) or []
    except:
        return load_json(ICS_FEEDS_FILE, [])

def save_cal_feeds(feeds):
    try:
        api('POST', 'user_settings',
            {'user_id': _get_user_id(), 'cal_feeds': feeds},
            {'Prefer': 'resolution=merge-duplicates'})
    except:
        pass
    save_json(ICS_FEEDS_FILE, feeds)

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


# ── ICS Feed parsing ──
ICS_CAL_COLORS = ['#9CAF9A','#C4A4A0','#A67B5B','#C4B99A','#7A9478','#B8A898']

def _parse_ics_dt(val, tzid=None):
    import calendar as _cal
    val = val.strip()
    is_utc = val.endswith('Z')
    val = val.replace('Z', '')
    for fmt in ('%Y%m%dT%H%M%S', '%Y%m%d'):
        try:
            dt = datetime.strptime(val, fmt)
            if is_utc:
                dt = datetime.fromtimestamp(_cal.timegm(dt.timetuple()))
            return dt
        except:
            pass
    return None

def _expand_rrule(dtstart, rrule_str, duration, entry_template, events, min_d, max_d):
    """Expand a recurring event into events dict for dates within [min_d, max_d]."""
    from datetime import timedelta
    rr = {}
    for part in rrule_str.split(';'):
        if '=' in part:
            k, v = part.split('=', 1)
            rr[k.strip()] = v.strip()
    freq = rr.get('FREQ', 'WEEKLY')
    interval = int(rr.get('INTERVAL', 1))
    max_count = int(rr.get('COUNT', 500))
    until = None
    if 'UNTIL' in rr:
        u = _parse_ics_dt(rr['UNTIL'][:8])  # just YYYYMMDD
        if u:
            until = u.date() if hasattr(u, 'date') else u

    cursor = dtstart.date() if hasattr(dtstart, 'date') else dtstart

    # If series ended before our window, skip entirely
    if until and not rr.get('COUNT') and until < min_d:
        return

    # Fast-forward for infinite events only (no COUNT).
    # COUNT events must iterate from start so n correctly tracks series end.
    if not rr.get('COUNT') and cursor < min_d:
        if freq == 'DAILY':
            days = (min_d - cursor).days
            cursor += timedelta(days=(days // interval) * interval)
        elif freq == 'WEEKLY':
            weeks = (min_d - cursor).days // 7
            cursor += timedelta(weeks=(weeks // interval) * interval)
        elif freq == 'MONTHLY':
            months = (min_d.year - cursor.year) * 12 + (min_d.month - cursor.month)
            months = max(0, months - 1)
            cursor = cursor.replace(year=cursor.year + (cursor.month + (months // interval) * interval - 1) // 12,
                                    month=(cursor.month + (months // interval) * interval - 1) % 12 + 1)
        elif freq == 'YEARLY':
            years = max(0, min_d.year - cursor.year - 1)
            cursor = cursor.replace(year=cursor.year + (years // interval) * interval)

    n = 0
    while cursor <= max_d and n < max_count:
        if until and cursor > until:
            break
        if cursor >= min_d:
            occ_start = datetime.combine(cursor, dtstart.time()) if hasattr(dtstart, 'time') else datetime(cursor.year, cursor.month, cursor.day)
            occ_end = occ_start + duration
            entry = dict(entry_template, start=occ_start, end=occ_end)
            events.setdefault(cursor.isoformat(), []).append(entry)
        n += 1
        if freq == 'DAILY':
            cursor += timedelta(days=interval)
        elif freq == 'WEEKLY':
            cursor += timedelta(weeks=interval)
        elif freq == 'MONTHLY':
            m = cursor.month - 1 + interval
            cursor = cursor.replace(year=cursor.year + m // 12, month=m % 12 + 1)
        elif freq == 'YEARLY':
            cursor = cursor.replace(year=cursor.year + interval)
        else:
            break

def parse_ics_mac(text, color):
    """Parse ICS text → dict of date_str -> [event_dict]"""
    from datetime import timedelta, date as _date
    events = {}
    today = datetime.now().date()
    min_d = today - timedelta(days=14)
    max_d = today + timedelta(days=180)

    # Unfold RFC 5545 continuation lines (CRLF + whitespace → nothing)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = __import__('re').sub(r'\n[ \t]', '', text)
    unfolded = text.splitlines()
    in_event = False
    ev = {}
    for line in unfolded:
        line = line.rstrip()
        if line == 'BEGIN:VEVENT':
            in_event = True; ev = {}
        elif line == 'END:VEVENT' and in_event:
            in_event = False
            dtstart = ev.get('DTSTART')
            title = ev.get('SUMMARY','(No title)')
            if dtstart:
                all_day = len(str(ev.get('DTSTART_RAW','')).strip()) == 8
                dtend = ev.get('DTEND') or dtstart
                duration = (dtend - dtstart) if isinstance(dtend, datetime) and isinstance(dtstart, datetime) else timedelta(0)
                entry = {'title': title, 'start': dtstart, 'end': dtend,
                         'all_day': all_day, 'calendar': ev.get('CAL_NAME',''),
                         'color': color, 'cal_id': 'ics_' + color}
                if ev.get('RRULE'):
                    _expand_rrule(dtstart, ev['RRULE'], duration, entry, events, min_d, max_d)
                else:
                    key = dtstart.date().isoformat()
                    if min_d <= dtstart.date() <= max_d:
                        events.setdefault(key, []).append(entry)
        elif in_event:
            if ':' in line:
                k, _, v = line.partition(':')
                k = k.split(';')[0].strip()
                if k == 'SUMMARY': ev['SUMMARY'] = v.strip()
                elif k == 'RRULE': ev['RRULE'] = v.strip()
                elif k in ('DTSTART','DTEND'):
                    raw = line.split(':',1)[1].strip()
                    ev[k+'_RAW'] = raw
                    ev[k] = _parse_ics_dt(raw)
    return events

def fetch_ics_feed(feed):
    url = feed['url'].replace('webcal://','https://')
    proxy_url = (f"{SUPABASE_URL}/functions/v1/ics-proxy?url={urllib.parse.quote(url, safe='')}")
    if feed.get('username'):
        proxy_url += f"&username={urllib.parse.quote(feed['username'])}&password={urllib.parse.quote(feed.get('password',''))}"
    req = urllib.request.Request(proxy_url, headers={**_auth_headers(), 'User-Agent': 'Taskwell/1.0'})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode('utf-8', errors='replace')
    if 'BEGIN:VCALENDAR' not in text:
        raise ValueError('Not a valid ICS feed')
    if not feed.get('name') or feed['name'] in ('Loading…', '⚠ Could not load'):
        m = __import__('re').search(r'X-WR-CALNAME:(.+)', text)
        feed['name'] = m.group(1).strip() if m else 'Calendar'
    return parse_ics_mac(text, feed['color'])

# ════════════════════════════════════════
# MAIN APP
# ════════════════════════════════════════
class TaskwellApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Taskwell")
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.minsize(400, 500)
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

    # ── Calendar (ICS only) ──
    def _init_calendar(self):
        self.cal_events_all = {}
        self.ics_events = {}
        self.ics_feeds = []
        threading.Thread(target=self._load_cal_feeds_bg, daemon=True).start()

    def get_cal_events(self, date_key):
        return self.ics_events.get(date_key, [])

    def _load_cal_feeds_bg(self):
        feeds = load_cal_feeds()
        self.root.after(0, self._on_cal_feeds_loaded, feeds)

    def _on_cal_feeds_loaded(self, feeds):
        self.ics_feeds = feeds
        self._refresh_ics_feeds()

    def _refresh_ics_feeds(self):
        if not self.ics_feeds:
            return
        def fetch():
            merged = {}
            for feed in self.ics_feeds:
                try:
                    evs = fetch_ics_feed(feed)
                    for k, arr in evs.items():
                        merged.setdefault(k, []).extend(arr)
                except Exception as e:
                    print(f"ICS feed error {feed.get('url')}: {e}")
            self.root.after(0, self._on_ics_loaded, merged)
        threading.Thread(target=fetch, daemon=True).start()

    def _on_ics_loaded(self, result):
        self.ics_events = result
        threading.Thread(target=save_cal_feeds, args=(self.ics_feeds,), daemon=True).start()
        if self.active_section == "week":
            self._render_week()
        elif self.active_section == "day":
            self._render_agenda()
        if hasattr(self, 'upcoming_frame'):
            self._render_mini_cal()

    # ── List context helpers ──
    def _ics_feeds_dialog(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("ICS Calendar Feeds")
        dlg.geometry("400x360")
        dlg.resizable(False, False)
        dlg.configure(bg=PAPER)
        dlg.transient(self.root)
        dlg.lift(); dlg.focus_force()

        list_frame = tk.Frame(dlg, bg=PAPER)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(16, 0))

        def refresh_list():
            for w in list_frame.winfo_children(): w.destroy()
            if not self.ics_feeds:
                tk.Label(list_frame, text="No feeds added yet.", font=FONT_SANS_SM,
                         bg=PAPER, fg=INK_FAINT).pack(anchor="w")
            for i, feed in enumerate(self.ics_feeds):
                row = tk.Frame(list_frame, bg=PAPER)
                row.pack(fill=tk.X, pady=2)
                color = feed.get('color', SAGE)
                tk.Label(row, text="●", fg=color, bg=PAPER, font=FONT_SANS_SM).pack(side=tk.LEFT)
                tk.Label(row, text=feed.get('name', feed['url'])[:40], font=FONT_SANS_SM,
                         bg=PAPER, fg=INK).pack(side=tk.LEFT, padx=6)
                idx = i
                tk.Button(row, text="✕", bg=PAPER, fg=INK_FAINT, font=FONT_SANS_SM,
                          relief=tk.FLAT, cursor="hand2",
                          command=lambda i=idx: remove_feed(i)).pack(side=tk.RIGHT)

        def remove_feed(i):
            self.ics_feeds.pop(i)
            threading.Thread(target=save_cal_feeds, args=(self.ics_feeds,), daemon=True).start()
            self.ics_events = {}
            refresh_list()
            self._render_week(); self._render_agenda()

        refresh_list()

        add_frame = tk.Frame(dlg, bg=PAPER)
        add_frame.pack(fill=tk.X, padx=20, pady=(12, 0))
        tk.Label(add_frame, text="Add ICS feed URL:", font=FONT_SANS_SM, bg=PAPER, fg=INK).pack(anchor="w")
        url_var = tk.StringVar()
        entry = tk.Entry(add_frame, textvariable=url_var, font=FONT_SANS_SM, bg=CREAM,
                         relief=tk.FLAT, highlightthickness=1, highlightbackground=CREAM_DARK)
        entry.pack(fill=tk.X, pady=4)
        status = tk.Label(add_frame, text="", font=FONT_SANS_SM, bg=PAPER, fg=RUST)
        status.pack(anchor="w")

        def add_feed():
            url = url_var.get().strip()
            if not url: return
            color = ICS_CAL_COLORS[len(self.ics_feeds) % len(ICS_CAL_COLORS)]
            feed = {'url': url, 'name': 'Loading…', 'color': color}
            self.ics_feeds.append(feed)
            threading.Thread(target=save_cal_feeds, args=(self.ics_feeds,), daemon=True).start()
            url_var.set('')
            status.config(text="Fetching…")
            refresh_list()
            def fetch():
                try:
                    evs = fetch_ics_feed(feed)
                    for k, arr in evs.items():
                        self.ics_events.setdefault(k, []).extend(arr)
                    self.root.after(0, lambda: (
                        status.config(text=f"Added: {feed['name']}"),
                        refresh_list(),
                        self._render_week(), self._render_agenda()
                    ))
                except Exception as e:
                    feed['name'] = '⚠ Could not load'
                    self.root.after(0, lambda: (
                        status.config(text=f"Error: {e}"),
                        refresh_list()
                    ))
            threading.Thread(target=fetch, daemon=True).start()

        entry.bind('<Return>', lambda e: add_feed())
        tk.Button(add_frame, text="Add Feed", bg=self.accent, fg=INK, font=FONT_SANS_BOLD,
                  relief=tk.FLAT, padx=12, pady=4, cursor="hand2",
                  command=add_feed).pack(pady=6)
        btn_row = tk.Frame(dlg, bg=PAPER)
        btn_row.pack(pady=(0, 14))
        tk.Button(btn_row, text="Save & Close", bg=self.accent, fg=INK, font=FONT_SANS_BOLD,
                  relief=tk.FLAT, padx=20, pady=6, cursor="hand2",
                  command=dlg.destroy).pack(side=tk.LEFT, padx=6)

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
        self._is_narrow = False

        # Status bar always at very bottom
        statusbar = tk.Frame(self.root, bg=CREAM_DARK)
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(statusbar, text=f"Taskwell · v {BUILD_TIMESTAMP}",
                 bg=CREAM_DARK, fg=INK_FAINT, font=("Helvetica Neue", 10),
                 anchor="center", pady=3).pack(fill=tk.X)
        self.status_var = tk.StringVar()
        tk.Label(statusbar, textvariable=self.status_var,
                 bg=CREAM_DARK, fg=INK_FAINT, font=FONT_SANS_SM,
                 anchor="e", padx=10).pack(fill=tk.X)

        self.sidebar = tk.Frame(self.root, bg=self.rail_bg, width=76)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        self.main_frame = tk.Frame(self.root, bg=PAPER)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sections = {}
        self._init_global_scroll()
        self._build_sidebar()
        self._build_hub()
        self._build_week()
        self._build_day()
        self._build_inbox()
        self._show_section("hub")
        self._active_scroll = (self.hub_canvas, 'y')

        self.root.bind('<Configure>', self._on_resize)
        # After startup settles, ensure sidebar is on the correct side
        self.root.after(200, self._fix_layout)

    NARROW_WIDTH = 650
    WIDE_WIDTH   = 1000  # 3-column threshold

    def _grid_cols(self):
        w = self.root.winfo_width()
        if w < self.NARROW_WIDTH: return 1
        if w >= self.WIDE_WIDTH:  return 3
        return 2

    def _on_resize(self, event):
        if event.widget is not self.root:
            return
        narrow = event.width < self.NARROW_WIDTH
        cols   = self._grid_cols()
        reflow = narrow != self._is_narrow
        self._is_narrow = narrow
        if reflow:
            self.sidebar.pack_forget()
            self.main_frame.pack_forget()
            if narrow:
                self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                self.sidebar.configure(width=0, height=56)
                self.sidebar.pack_propagate(True)
                self.sidebar.pack(side=tk.BOTTOM, fill=tk.X)
            else:
                self.sidebar.configure(width=76, height=0)
                self.sidebar.pack_propagate(False)
                self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
                self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._build_sidebar()
        # Re-render hub if column count changed
        prev_cols = getattr(self, '_last_cols', None)
        if cols != prev_cols:
            self._last_cols = cols
            if self.active_section == 'hub':
                self._render_hub()

    def _fix_layout(self):
        """Correct the sidebar position after startup geometry settles."""
        w = self.root.winfo_width()
        narrow = w < self.NARROW_WIDTH
        if narrow != self._is_narrow:
            self._is_narrow = narrow
            self.sidebar.pack_forget()
            self.main_frame.pack_forget()
            if narrow:
                self.main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                self.sidebar.configure(width=0, height=56)
                self.sidebar.pack_propagate(True)
                self.sidebar.pack(side=tk.BOTTOM, fill=tk.X)
            else:
                self.sidebar.configure(width=76, height=0)
                self.sidebar.pack_propagate(False)
                self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
                self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self._build_sidebar()

    def _build_sidebar(self):
        for w in self.sidebar.winfo_children():
            w.destroy()
        bg = self.rail_bg
        narrow = self._is_narrow

        if narrow:
            self._build_sidebar_narrow(bg)
        else:
            self._build_sidebar_wide(bg)

    def _build_sidebar_wide(self, bg):
        mark = tk.Label(self.sidebar, text="✓", bg=CREAM, fg=self.accent,
                        font=("Georgia", 14, "bold"), width=2, pady=6, cursor="hand2",
                        relief=tk.RAISED if self.current_context == "all" else tk.FLAT)
        mark.pack(pady=(16, 8), padx=10)
        mark.bind("<Button-1>", lambda e: self._set_context("all"))

        for ctx, icon, label in [("work", "⊛", "Work"), ("home", "⌂", "Home")]:
            is_active = self.current_context == ctx
            f = tk.Frame(self.sidebar, bg=CREAM if is_active else bg, cursor="hand2")
            f.pack(pady=2, padx=8, fill=tk.X)
            f.bind("<Button-1>", lambda e, c=ctx: self._set_context(c))
            for text, font in [(icon, ("Helvetica Neue", 16)), (label, FONT_SANS_SM)]:
                lbl = tk.Label(f, text=text, bg=CREAM if is_active else bg, fg=INK, font=font, pady=2)
                lbl.pack()
                lbl.bind("<Button-1>", lambda e, c=ctx: self._set_context(c))

        tk.Frame(self.sidebar, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=12, pady=8)

        self.tab_buttons = {}
        for key, icon, label in [("hub","⊞","Hub"),("week","◫","Week"),("day","◷","Day"),("inbox","✉","Inbox")]:
            is_active = self.active_section == key
            f = tk.Frame(self.sidebar, bg=ROSE_PALE if is_active else bg, cursor="hand2")
            f.pack(pady=3, padx=8, fill=tk.X)
            f.bind("<Button-1>", lambda e, k=key: self._show_section(k))
            for text, font in [(icon, ("Helvetica Neue", 18)), (label, FONT_SANS_SM)]:
                lbl = tk.Label(f, text=text, bg=ROSE_PALE if is_active else bg, fg=INK, font=font, pady=3)
                lbl.pack()
                lbl.bind("<Button-1>", lambda e, k=key: self._show_section(k))
            self.tab_buttons[key] = f

    def _build_sidebar_narrow(self, bg):
        # Horizontal bottom bar matching web mobile layout
        mark = tk.Label(self.sidebar, text="✓", bg=CREAM, fg=self.accent,
                        font=("Georgia", 13, "bold"), padx=8, pady=6, cursor="hand2",
                        relief=tk.RAISED if self.current_context == "all" else tk.FLAT)
        mark.pack(side=tk.LEFT, padx=(6, 2), pady=4)
        mark.bind("<Button-1>", lambda e: self._set_context("all"))

        for ctx, icon in [("work", "⊛"), ("home", "⌂")]:
            is_active = self.current_context == ctx
            f = tk.Label(self.sidebar, text=icon, bg=CREAM if is_active else bg,
                         fg=INK, font=("Helvetica Neue", 18), padx=6, pady=4, cursor="hand2")
            f.pack(side=tk.LEFT, padx=2)
            f.bind("<Button-1>", lambda e, c=ctx: self._set_context(c))

        tk.Frame(self.sidebar, bg=CREAM_DARK, width=1).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=8)

        self.tab_buttons = {}
        for key, icon, label in [("hub","⊞","Hub"),("week","◫","Week"),("day","◷","Day"),("inbox","✉","Inbox")]:
            is_active = self.active_section == key
            f = tk.Frame(self.sidebar, bg=ROSE_PALE if is_active else bg, cursor="hand2")
            f.pack(side=tk.LEFT, padx=3, pady=4)
            f.bind("<Button-1>", lambda e, k=key: self._show_section(k))
            for text, font in [(icon, ("Helvetica Neue", 16)), (label, ("Helvetica Neue", 8))]:
                lbl = tk.Label(f, text=text, bg=ROSE_PALE if is_active else bg, fg=INK, font=font, padx=6)
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
        self._hub_win = self.hub_canvas.create_window((0, 0), window=self.hub_scroll_frame, anchor="nw")
        self.hub_canvas.bind("<Configure>",
            lambda e: self.hub_canvas.itemconfig(self._hub_win, width=e.width))
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
                cols = self._grid_cols()
                grid = tk.Frame(self.hub_scroll_frame, bg=PAPER)
                grid.pack(fill=tk.X, padx=20, pady=(8, 0))
                for c in range(cols):
                    grid.columnconfigure(c, weight=1, uniform="col")
                for i, lst in enumerate(visible):
                    r, c = divmod(i, cols)
                    cell = tk.Frame(grid, bg=CREAM, highlightthickness=1,
                                    highlightbackground=CREAM_DARK)
                    cell.grid(row=r, column=c, sticky="nsew",
                              padx=(0, 6 if c < cols - 1 else 0), pady=(0, 6))
                    self._render_list_block(cell, lst)
        else:
            for sec in WORK_SECTIONS:
                sec_lists = [l for l in self.lists
                             if l.get("section", "Misc") == sec and self.get_list_ctx(l) == "work"]
                if self.current_context == "work" or sec_lists:
                    self._render_section_block(self.hub_scroll_frame, sec, sec, sec_lists)

        self.hub_canvas.update_idletasks()
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

        cols = self._grid_cols()
        grid = tk.Frame(sec_frame, bg=PAPER)
        grid.pack(fill=tk.X)
        for c in range(cols):
            grid.columnconfigure(c, weight=1, uniform="col")

        for i, lst in enumerate(sec_lists):
            r, c = divmod(i, cols)
            cell = tk.Frame(grid, bg=CREAM, bd=0,
                            highlightthickness=1, highlightbackground=CREAM_DARK)
            cell.grid(row=r, column=c, sticky="nsew",
                      padx=(0, 6 if c < cols - 1 else 0), pady=(0, 6))
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

        # Task input row — underline style, matches web app
        tk.Frame(block, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=10, pady=(6, 0))
        input_row = tk.Frame(block, bg=bg)
        input_row.pack(fill=tk.X, padx=10, pady=(2, 0))
        tk.Frame(block, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=10)
        tk.Frame(block, bg=bg, height=6).pack(fill=tk.X)

        task_entry = tk.Entry(input_row, font=("Georgia", 10), bg=bg, fg=INK_SOFT,
                              relief=tk.FLAT, bd=0, insertbackground=INK,
                              highlightthickness=0)
        task_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2, ipadx=4)

        # Vertical divider between task and date fields
        tk.Frame(input_row, bg=CREAM_DARK, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=2)

        due_var = make_date_var()
        due_entry = tk.Entry(input_row, textvariable=due_var, font=("Helvetica Neue", 9),
                             bg=bg, fg=INK_SOFT,
                             relief=tk.FLAT, bd=0, insertbackground=INK, width=7,
                             highlightthickness=0)
        due_entry.pack(side=tk.LEFT, padx=(4, 0), ipady=2, ipadx=3)

        def add(lid=list_id, te=task_entry, dv=due_var):
            self._add_task(lid, te, dv)

        task_entry.bind("<Return>", lambda e: add())
        tk.Button(input_row, text="+", bg=self.accent, fg=INK, font=FONT_SANS_BOLD,
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
        # Optimistic: add locally right away so UI updates instantly
        tmp_id = f"_tmp_{id(title)}"
        tmp = {"id": tmp_id, "list_id": list_id, "title": title,
               "completed": False, "due_date": due_date}
        self.tasks.append(tmp)
        self._render_hub()
        if self.active_section == "week":
            self._render_week()
        body = {"list_id": list_id, "title": title, "completed": False,
                "due_date": due_date, "user_id": _get_user_id()}
        api_bg("POST", "tasks", body,
               callback=lambda r, e: self.root.after(0, self._on_task_added, tmp_id, r, e))

    def _on_task_added(self, tmp_id, result, error):
        # Remove the temp task
        self.tasks = [t for t in self.tasks if t["id"] != tmp_id]
        if error:
            self.status_var.set(f"Error saving task: {error}")
            self._render_hub()
            return
        # Replace with real server task if returned, otherwise reload
        if result and isinstance(result, list) and result:
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
            api_bg("POST", "lists", {"name": name, "section": section, "context": context, "user_id": _get_user_id()},
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
        self.today_btn = tk.Button(nav, text="Today", bg=self.accent, fg=INK, font=FONT_SANS_SM,
                                   relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                                   command=lambda: self._week_nav(0))
        # Today button packed conditionally in _render_week
        tk.Button(nav, text="Next ›", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                  relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=lambda: self._week_nav(1)).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(nav, text="Calendar Feeds", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                  relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=self._ics_feeds_dialog).pack(side=tk.RIGHT)

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
                         bg=ev["color"], fg=INK, wraplength=130,
                         anchor="w", justify=tk.LEFT).pack(anchor="w")
                if not ev["all_day"]:
                    t_str = ev["start"].strftime("%-I:%M") + "–" + ev["end"].strftime("%-I:%M %p")
                    tk.Label(ev_f, text=t_str, font=FONT_SANS_SM,
                             bg=ev["color"], fg=INK_SOFT).pack(anchor="w")

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
        tk.Button(hdr, text="Calendar Feeds", bg=CREAM, fg=INK, font=FONT_SANS_SM,
                  relief=tk.RAISED, padx=8, pady=2, cursor="hand2",
                  activebackground=CREAM_DARK,
                  command=self._ics_feeds_dialog).pack(side=tk.RIGHT)

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
        self._day_win = self.day_canvas.create_window((0, 0), window=self.day_scroll_frame, anchor="nw")
        self.day_canvas.bind("<Configure>",
            lambda e: self.day_canvas.itemconfig(self._day_win, width=e.width))
        self.day_canvas.configure(yscrollcommand=day_scroll.set)
        day_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.day_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._register_scroll(self.day_canvas, 'y')

        # Sidebar: mini-cal
        sidebar = tk.Frame(split, bg=CREAM, width=340)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Mini-cal header
        cal_nav = tk.Frame(sidebar, bg=CREAM)
        cal_nav.pack(fill=tk.X, padx=10, pady=(12, 6))
        tk.Button(cal_nav, text="‹", bg=CREAM, fg=INK, font=("Helvetica Neue", 14),
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  command=self._mini_cal_prev).pack(side=tk.LEFT)
        self.mini_cal_title = tk.Label(cal_nav, text="", font=("Helvetica Neue", 15, "bold"),
                                       bg=CREAM, fg=INK)
        self.mini_cal_title.pack(side=tk.LEFT, expand=True)
        tk.Button(cal_nav, text="›", bg=CREAM, fg=INK, font=("Helvetica Neue", 14),
                  relief=tk.FLAT, bd=0, cursor="hand2",
                  command=self._mini_cal_next).pack(side=tk.RIGHT)

        # Mini-cal grid (rebuilt in _render_mini_cal)
        self.mini_cal_grid_frame = tk.Frame(sidebar, bg=CREAM)
        self.mini_cal_grid_frame.pack(fill=tk.X, padx=8)

        tk.Frame(sidebar, bg=CREAM_DARK, height=1).pack(fill=tk.X, padx=12, pady=(14, 0))
        tk.Label(sidebar, text="UPCOMING", font=("Helvetica Neue", 10, "bold"),
                 bg=CREAM, fg=INK_FAINT).pack(anchor="w", padx=16, pady=(8, 4))
        self.upcoming_frame = tk.Frame(sidebar, bg=CREAM)
        self.upcoming_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))

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
            tk.Label(self.mini_cal_grid_frame, text=d, font=("Helvetica Neue", 12, "bold"),
                     bg=CREAM, fg=INK_FAINT, width=4).grid(row=0, column=i, pady=(0, 4))

        first_day = date(year, month, 1)
        start_col = first_day.weekday() + 1  # Monday=0 → col 1; Sunday → col 0
        start_col = first_day.isoweekday() % 7  # Sunday=0

        # Previous month padding
        for col in range(start_col):
            d = first_day - timedelta(days=start_col - col)
            tk.Label(self.mini_cal_grid_frame, text=str(d.day), font=("Helvetica Neue", 13),
                     bg=CREAM, fg=INK_FAINT, width=4).grid(row=1, column=col)

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

            lbl = tk.Label(self.mini_cal_grid_frame, text=str(d), font=("Helvetica Neue", 13),
                           bg=bg, fg=fg, width=4, cursor="hand2",
                           relief=tk.FLAT, bd=1)
            lbl.grid(row=row, column=col, padx=2, pady=2)
            lbl.bind("<Button-1>", lambda e, k=key: self._select_day(k))

            if has_tasks and not is_selected:
                lbl.configure(text=f"{d}·")

            col += 1
            if col == 7:
                col = 0
                row += 1

        # Upcoming events — next 7 days
        for w in self.upcoming_frame.winfo_children():
            w.destroy()
        today = date.today()
        shown = 0
        for offset in range(8):
            day = today + timedelta(days=offset)
            evs = self.get_cal_events(day.isoformat())
            if not evs:
                continue
            day_lbl = "Today" if offset == 0 else ("Tomorrow" if offset == 1 else day.strftime("%a, %b %-d"))
            tk.Label(self.upcoming_frame, text=day_lbl,
                     font=("Helvetica Neue", 10, "bold"), bg=CREAM, fg=INK_SOFT
                     ).pack(anchor="w", pady=(6 if shown else 0, 1))
            for ev in sorted(evs, key=lambda e: (e["all_day"], e["start"])):
                t = "" if ev["all_day"] else ev["start"].strftime("%-I:%M %p").lower() + "  "
                tk.Label(self.upcoming_frame, text=f"{t}{ev['title']}",
                         font=("Helvetica Neue", 11), bg=CREAM, fg=INK,
                         wraplength=280, justify="left", anchor="w"
                         ).pack(fill=tk.X, anchor="w")
            shown += 1

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
                row.pack(fill=tk.X, padx=10, pady=2)
                if ev["all_day"]:
                    time_str = "All day"
                else:
                    time_str = (ev["start"].strftime("%-I:%M") +
                                "–" + ev["end"].strftime("%-I:%M %p"))
                tk.Label(row, text=time_str, font=FONT_SANS_SM, bg=ev["color"],
                         fg=INK_SOFT, padx=10, pady=6, anchor="w").pack(side=tk.LEFT)
                tk.Label(row, text=ev["title"], font=FONT_SERIF_SM, bg=ev["color"],
                         fg=INK, padx=6, pady=6, anchor="w"
                         ).pack(side=tk.LEFT, fill=tk.X, expand=True)

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
        self._inbox_win = self.inbox_canvas.create_window((0, 0), window=self.inbox_scroll_frame, anchor="nw")
        self.inbox_canvas.bind("<Configure>",
            lambda e: self.inbox_canvas.itemconfig(self._inbox_win, width=e.width))
        self.inbox_canvas.configure(yscrollcommand=inbox_scroll.set)
        inbox_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.inbox_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._register_scroll(self.inbox_canvas, 'y')

    def _render_inbox(self):
        for w in self.inbox_scroll_frame.winfo_children():
            w.destroy()

        ctx = self.current_context
        visible = [item for item in self.inbox_items
                   if ctx == "all" or item.get("context", "work") == ctx]

        if not visible:
            label = "No items." if not self.inbox_items else f"No {ctx} items."
            tk.Label(self.inbox_scroll_frame,
                     text=label + " Add tasks you need to assign to a list.",
                     font=("Georgia", 12, "italic"), bg=PAPER, fg=INK_FAINT
                     ).pack(anchor="w", padx=20, pady=16)
        else:
            for i, item in enumerate(visible):
                i = self.inbox_items.index(item)  # real index for mutations
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

        self.inbox_canvas.update_idletasks()
        self.inbox_canvas.configure(scrollregion=self.inbox_canvas.bbox("all"))

    def _add_inbox_item(self):
        val = self.inbox_entry.get().strip()
        if not val:
            return
        self.inbox_entry.delete(0, tk.END)
        ctx = self.current_context if self.current_context != "all" else "work"
        self.inbox_items.insert(0, {"text": val, "done": False, "context": ctx})
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
                   {"list_id": chosen["id"], "title": item["text"], "completed": False, "user_id": _get_user_id()},
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


def _show_login(root):
    win = tk.Toplevel(root)
    win.title("Sign in to Taskwell")
    win.geometry("340x220")
    win.resizable(False, False)
    win.configure(bg=CREAM)
    win.grab_set()

    tk.Label(win, text="Taskwell", font=("Georgia", 22), bg=CREAM, fg=INK).pack(pady=(30, 4))
    tk.Label(win, text="Sign in to access your tasks", font=("Helvetica Neue", 12),
             bg=CREAM, fg=INK_SOFT).pack()

    status = tk.Label(win, text="", font=("Helvetica Neue", 11), bg=CREAM, fg=RUST, wraplength=300)
    status.pack(pady=8)

    btn = tk.Button(win, text="Sign in with Google", font=("Helvetica Neue", 13, "bold"),
                    bg=SAGE, fg=INK, relief="flat", padx=16, pady=8, cursor="hand2",
                    command=lambda: _do_login(win, btn, status, root))
    btn.pack(pady=4)

def _do_login(win, btn, status, root):
    btn.config(state="disabled", text="Opening browser…")
    status.config(text="")

    def on_success():
        root.after(0, lambda: (win.destroy(), TaskwellApp(root)))

    def on_error(msg):
        root.after(0, lambda: (
            btn.config(state="normal", text="Sign in with Google"),
            status.config(text=msg)
        ))

    login_with_google(on_success, on_error)

def main():
    root = tk.Tk()
    root.title("Taskwell")
    root.withdraw()
    try:
        root.createcommand('tk::mac::ReopenApplication', root.deiconify)
    except:
        pass

    if is_logged_in():
        root.deiconify()
        TaskwellApp(root)
    else:
        root.deiconify()
        _show_login(root)

    root.mainloop()


if __name__ == "__main__":
    main()
