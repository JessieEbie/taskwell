#!/usr/bin/env python3
"""
Taskwell — Mac App (WebView)
Loads the Taskwell web app in a native macOS window via pywebview.
Updates to the web app are automatically reflected — no rebuild needed.
"""
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import webview

PORT = 37842
_window = None


class CallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # suppress server logs

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
        'https://jessieebie.github.io/taskwell/',
        width=1280,
        height=860,
        min_size=(375, 600),
        text_select=False,
        js_api=api,
    )

    t = threading.Thread(target=start_callback_server, daemon=True)
    t.start()

    def on_loaded():
        _window.evaluate_js(f'window.__GCAL_REDIRECT_PORT__ = {PORT};')

    _window.events.loaded += on_loaded

    webview.start(
        debug=False,
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    )


if __name__ == '__main__':
    main()
