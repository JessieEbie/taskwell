# Taskwell — Setup Instructions

## Files in this folder
- `taskwell_mac.py` — the Mac app
- `setup.py` — used to build the clickable app
- `launch_taskwell.sh` — optional quick launcher
- `README.md` — this file

---

## Step 1: Run it right now (Terminal)
Open Terminal and type:
```
python3 /Applications/Taskwell\ app/taskwell_mac.py
```

---

## Step 2: Build a real clickable Mac app

Open Terminal and run these one at a time:

**Install py2app:**
```
pip3 install py2app
```

**Navigate to your Taskwell folder:**
```
cd /Applications/Taskwell\ app
```

**Build the app:**
```
python3 setup.py py2app
```

When it finishes, look inside the new `dist` folder — you'll find `Taskwell.app`.
Drag it to your main Applications folder and you're done!
It will show up in Spotlight and you can add it to your Dock.

---

## iPad / iPhone
1. Open `taskwell.html` in Safari
2. Tap Share → "Add to Home Screen"
3. Name it Taskwell and tap Add
4. Opens full screen like a real app!

---

## Sync
Both the Mac app and the iPad web app talk to the same Supabase database.
Tasks sync automatically between devices.
Capture notes and quick items are saved locally on each device.
