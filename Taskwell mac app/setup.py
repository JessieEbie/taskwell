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
    # No setup_requires=['py2app'] — it's deprecated, and it makes setuptools
    # walk every installed distribution's metadata to decide whether the
    # requirement is already satisfied. One malformed entry in site-packages
    # (a dist whose name reads back as None) is enough to crash that walk and
    # fail the build outright. py2app is installed anyway, and it registers the
    # "py2app" command through entry points, so this line bought nothing.
)
