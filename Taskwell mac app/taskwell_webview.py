#!/usr/bin/env python3
"""
Taskwell — Mac App (WebView)
Loads the Taskwell web app in a native macOS window via pywebview.
Updates to the web app are automatically reflected — no rebuild needed.
"""
import webview

def main():
    window = webview.create_window(
        'Taskwell',
        'https://jessieebie.github.io/taskwell/',
        width=1280,
        height=860,
        min_size=(375, 600),
        text_select=False,
    )
    webview.start(
        debug=False,
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15',
    )

if __name__ == '__main__':
    main()
