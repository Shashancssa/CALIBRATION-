# CALIBRATION-
CALIBRATION 

## First-time Windows setup

If `python app.py` shows `ModuleNotFoundError: No module named 'flask'`, the Python packages have not been installed in the Python environment being used to run the app.

From the project folder, run either of these options:

### Option 1: Automatic setup

Double-click `setup_windows.bat`, or run:

```bat
setup_windows.bat
```

Then start the app with:

```bat
run_windows.bat
```

### Option 2: Manual setup

```bat
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open the app in the browser at `http://127.0.0.1:5000`.

> Important: install packages and run `app.py` using the same Python executable. Using `.venv\Scripts\python.exe` avoids installing Flask into one Python version and running another Python version by mistake.

## Build Windows EXE (for local launch)

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build executable from project root:
   ```bash
   pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" app.py --name "Kaynes calibration maste"
   ```
3. EXE output path:
   - `dist/Kaynes calibration maste.exe`

## Run on company network

Set host to `0.0.0.0` so other systems in LAN can open it:

```bash
set FLASK_HOST=0.0.0.0
set FLASK_PORT=5000
python app.py
```

Then users can open:
- `http://<server-ip>:5000`

To open by name (example: `Kaynes calibration maste`), map DNS/hosts in your network to the server IP.

## Change automatic mail schedule time

The alert email job runs once per day. By default it runs at **09:00 AM** (Asia/Kolkata).

To change the time, set these environment variables before starting `app.py`:

```bash
set AUTO_MAIL_HOUR=10
set AUTO_MAIL_MINUTE=30
python app.py
```

Example above runs the automatic email at **10:30 AM** daily.
