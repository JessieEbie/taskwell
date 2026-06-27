from setuptools import setup
import os

APP = ['taskwell_mac.py']
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.png',
    'plist': {
        'CFBundleName': 'Taskwell',
        'CFBundleDisplayName': 'Taskwell',
        'CFBundleIdentifier': 'com.jessie.taskwell',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0',
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
    },
    'packages': ['tkinter'],
}

setup(
    app=APP,
    name='Taskwell',
    data_files=[],
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
