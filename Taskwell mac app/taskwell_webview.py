#!/usr/bin/env python3
"""
Taskwell — Mac App (WebView)
Loads the Taskwell web app in a native macOS window via pywebview.
Updates to the web app are automatically reflected — no rebuild needed.
"""
import base64
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import webview

PORT = 37842
_window = None

_icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
with open(_icon_path, 'rb') as _f:
    _ICON_B64 = base64.b64encode(_f.read()).decode()

SPLASH_HTML = f'''<!DOCTYPE html>
<html><head><style>
* {{ margin:0;padding:0;box-sizing:border-box }}
body {{ background:#C4A4A0;display:flex;align-items:center;justify-content:center;height:100vh;font-family:-apple-system,sans-serif }}
.card {{ background:#FAF7F2;border-radius:20px;padding:36px 28px;width:320px;text-align:center;box-shadow:0 20px 60px rgba(46,33,24,.15) }}
img {{ width:72px;height:72px;border-radius:16px;display:block;margin:0 auto 16px }}
h1 {{ font-size:24px;font-weight:normal;color:#2E2118;margin-bottom:6px }}
p {{ font-size:12px;color:#6B5744 }}
</style></head>
<body>
<div class="card">
  <img src="data:image/png;base64,{_ICON_B64}">
  <h1>Taskwell</h1>
  <p>Loading…</p>
</div>
<script>
setTimeout(function() {{
  window.location.replace('https://jessieebie.github.io/taskwell/');
}}, 400);
</script>
</body></html>'''


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
            _window.evaluate_js(f"processGcalCallback('{safe_code}', '{safe_state}')")


class MacAPI:
    def open_google_auth(self, url):
        webbrowser.open(url)
        return True


def start_callback_server():
    server = HTTPServer(('127.0.0.1', PORT), CallbackHandler)
    server.serve_forever()


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

    def on_loaded():
        if 'jessieebie.github.io' in (_window.get_current_url() or ''):
            _window.evaluate_js(f'window.__GCAL_REDIRECT_PORT__ = {PORT};')

    _window.events.loaded += on_loaded

    storage = os.path.expanduser('~/Library/Application Support/Taskwell')
    os.makedirs(storage, exist_ok=True)

    webview.start(
        debug=False,
        private_mode=False,
        storage_path=storage,
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    )


if __name__ == '__main__':
    main()
