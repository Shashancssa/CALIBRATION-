# CALIBRATION-
CALIBRATION 

## Build Windows EXE (for local launch)

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Build executable from project root:
   ```bash
   pyinstaller --onefile --add-data "templates;templates" app.py --name "Kaynes calibration maste"
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
