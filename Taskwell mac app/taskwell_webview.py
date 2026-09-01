#!/usr/bin/env python3
"""
Taskwell — Mac App (WebView)
Loads the Taskwell web app in a native macOS window via pywebview.
Updates to the web app are automatically reflected — no rebuild needed.
"""
import base64
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import webview

PORT = 37842
_window = None

import sys as _sys
if getattr(_sys, 'frozen', False):
    _resources = os.path.join(os.path.dirname(_sys.executable), '..', 'Resources')
else:
    _resources = os.path.dirname(os.path.abspath(__file__))
_icon_path = os.path.join(_resources, 'icon.png')
with open(_icon_path, 'rb') as _f:
    _ICON_B64 = base64.b64encode(_f.read()).decode()

APP_URL = 'https://jessieebie.github.io/taskwell/'

# The window shows this local card first, then navigates to the live app.
#
# That navigation used to be a single blind location.replace() with no timeout,
# no error state and no retry — so if it stalled (most commonly because the Mac
# had only just woken and the network wasn't ready yet), the app sat on
# "Loading…" forever with no indication of what was wrong and no way out but
# force-quitting. It now times the navigation out, retries itself, goes again
# the moment connectivity returns, and finally offers a Try again button.
#
# Built with .replace() rather than an f-string so the CSS/JS braces don't all
# have to be doubled — that escaping is easy to get subtly wrong.
SPLASH_HTML = '''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* { margin:0;padding:0;box-sizing:border-box }
body { background:#C4A4A0;display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,sans-serif }
.card { background:#FAF7F2;border-radius:20px;padding:36px 28px;width:320px;text-align:center;box-shadow:0 20px 60px rgba(46,33,24,.15) }
img { width:72px;height:72px;border-radius:16px;display:block;margin:0 auto 16px }
h1 { font-size:24px;font-weight:normal;color:#2E2118;margin-bottom:6px }
p { font-size:12px;color:#6B5744;line-height:1.5 }
button { margin-top:16px;font-size:13px;padding:10px 20px;min-height:44px;border-radius:10px;
         border:1.5px solid #A67B5B;background:#A67B5B;color:#FAF7F2;cursor:pointer }
button[hidden] { display:none }
</style></head>
<body>
<div class="card">
  <img src="data:image/png;base64,__ICON__">
  <h1>Taskwell</h1>
  <p id="msg">Loading…</p>
  <button id="retry" hidden onclick="go(true)">Try again</button>
</div>
<script>
var TARGET = '__TARGET__';
var LOAD_TIMEOUT_MS = 8000;
var AUTO_RETRIES = 2;
var attempt = 0, timer = null;

function msg(t) { document.getElementById('msg').textContent = t; }

function stalled() {
  // Only ever reached if the navigation never took: a successful load tears
  // this document down, and this timer along with it.
  if (attempt <= AUTO_RETRIES) { go(false); return; }
  msg(navigator.onLine
    ? 'Could not reach Taskwell. It may be temporarily unavailable.'
    : 'You appear to be offline. Taskwell will load as soon as you reconnect.');
  document.getElementById('retry').hidden = false;
}

function go(manual) {
  if (timer) { clearTimeout(timer); timer = null; }
  attempt++;
  document.getElementById('retry').hidden = true;
  msg(attempt === 1 || manual ? 'Loading…' : 'Still trying…');
  timer = setTimeout(stalled, LOAD_TIMEOUT_MS);
  window.location.replace(TARGET);
}

// Go again the instant the network returns, rather than making her click.
window.addEventListener('online', function () { go(true); });

setTimeout(function () { go(false); }, 400);
</script>
</body></html>'''.replace('__ICON__', _ICON_B64).replace('__TARGET__', APP_URL)


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        code = params.get('code', [''])[0]
        state = params.get('state', [''])[0]

        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'''<!DOCTYPE html>
<html><body style="font-family:-apple-system,sans-serif;text-align:center;padding:60px;color:#333">
<h2>Connected to Taskwell!</h2>
<p>You can close this tab and return to the Taskwell app.</p>
<script>window.close();</script>
</body></html>''')

        if code and _window:
            safe_code = code.replace("'", "\\'")
            safe_state = state.replace("'", "\\'")
            # Both Google and Outlook connect flows share this one local
            # callback port (see connectGoogleCalendar/connectOutlookCalendar
            # in taskwell.html) — state tells us which one just completed.
            handler = 'processOutlookCallback' if state == 'outlook_auth' else 'processGcalCallback'
            _window.evaluate_js(f"{handler}('{safe_code}', '{safe_state}')")


class MacAPI:
    # Name is Google-specific from when this was written, but it's a generic
    # "open this URL in the system browser" bridge — reused by Outlook's
    # connect flow too (see connectOutlookCalendar in taskwell.html).
    def open_google_auth(self, url):
        webbrowser.open(url)
        return True


def start_callback_server():
    server = HTTPServer(('127.0.0.1', PORT), CallbackHandler)
    server.serve_forever()


def navigation_watchdog():
    """Second safety net behind the splash's own JS retry.

    The splash retries itself, but only while it is still the live document —
    if the webview swaps it out for its own "cannot open page" error, those
    timers die with it and the window is stuck for good. From out here we can
    still see the window is not on the app and push it there again.
    """
    for _ in range(6):
        time.sleep(15)
        try:
            if 'jessieebie.github.io' in (_window.get_current_url() or ''):
                return  # made it; nothing to do
            _window.load_url(APP_URL)
        except Exception:
            return  # window closed, or this pywebview build lacks the API


def main():
    global _window
    api = MacAPI()

    _window = webview.create_window(
        'Taskwell',
        html=SPLASH_HTML,
        width=1280,
        height=860,
        min_size=(375, 600),
        text_select=False,
        js_api=api,
    )

    t = threading.Thread(target=start_callback_server, daemon=True)
    t.start()

    threading.Thread(target=navigation_watchdog, daemon=True).start()

    def on_loaded():
        if 'jessieebie.github.io' in (_window.get_current_url() or ''):
            _window.evaluate_js(f'window.__GCAL_REDIRECT_PORT__ = {PORT};')

    _window.events.loaded += on_loaded

    storage = os.path.expanduser('~/Library/Application Support/Taskwell')
    os.makedirs(storage, exist_ok=True)

    # pywebview's default macOS menu bar includes a standard Edit menu with
    # Undo/Redo bound to Cmd+Z/Cmd+Shift+Z. As a native menu key-equivalent it
    # intercepts the keystroke before it ever reaches the page, so Taskwell's
    # own Cmd+Z undo (completing/deleting a task, etc.) never fires. Passing
    # an empty menu list suppresses that default Edit menu so Cmd+Z falls
    # through to the web app instead. Standard text editing (Cmd+C/V/X,
    # right-click Cut/Copy/Paste) is handled by WKWebView itself and isn't
    # affected by the app-level menu.
    webview.start(
        debug=False,
        private_mode=False,
        storage_path=storage,
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
        menu=[],
    )


if __name__ == '__main__':
    main()
