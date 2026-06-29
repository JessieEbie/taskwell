from setuptools import setup
import os

APP = ['taskwell_webview.py']
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.png',
    'plist': {
        'CFBundleName': 'Taskwell',
        'CFBundleDisplayName': 'Taskwell',
        'CFBundleIdentifier': 'com.jessie.taskwell',
        'CFBundleVersion': '1.1.0',
        'CFBundleShortVersionString': '1.1',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
    'packages': ['webview'],
    'includes': ['objc', 'Foundation', 'AppKit', 'WebKit'],
}

setup(
    app=APP,
    name='Taskwell',
    data_files=[],
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
