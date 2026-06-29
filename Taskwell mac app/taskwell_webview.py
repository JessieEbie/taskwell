#!/usr/bin/env python3
"""
Taskwell — Mac App (WebView)
Wraps taskwell.html in a native macOS window via pywebview.
"""
import os
import sys
import webview

def main():
    # Find taskwell.html — works both in dev (sibling file) and bundled .app
    if getattr(sys, 'frozen', False):
        # Running inside .app bundle — html is in Resources
        base = os.path.dirname(sys.executable)
        html_path = os.path.join(base, '..', 'Resources', 'taskwell.html')
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(base, '..', 'taskwell.html')

    html_path = os.path.normpath(html_path)
    if not os.path.exists(html_path):
        # Fallback: look next to this script
        html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'taskwell.html')

    url = 'file://' + html_path

    window = webview.create_window(
        'Taskwell',
        url,
        width=1280,
        height=860,
        min_size=(375, 600),
        text_select=False,
    )
    webview.start(debug=False)

if __name__ == '__main__':
    main()
