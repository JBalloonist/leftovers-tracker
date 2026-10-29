# Leftovers Tracker

Track leftovers in the fridge with QR labels. Scan a label with your phone, say or type what's in
the container, and the app saves the name with the date and time. Scan it again to mark it eaten or
tossed, which frees the label for reuse.

## Run locally

Packages are managed with [uv](https://docs.astral.sh/uv/).

```sh
uv sync                  # creates .venv from uv.lock
uv run app.py            # http://localhost:5000, password "leftovers"
uv run pytest -q
uv add <package>         # add a dependency (updates pyproject.toml and uv.lock)
```

The phone camera and mic need HTTPS, so test scanning on the deployed site.

## Deploy to PythonAnywhere

1. Create an account. You get `https://<username>.pythonanywhere.com` with HTTPS.
2. Open a **Bash console** and upload the code (`git clone`, or upload a zip through the **Files** tab):
   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.bashrc
   cd ~ && git clone <your-repo> leftovers-tracker
   cd leftovers-tracker
   uv sync --no-dev --python 3.12
   ```
   Run `git pull && uv sync --no-dev` after future updates, then reload the web app.
3. On the **Web** tab, click **Add a new web app**, choose **Manual configuration**, then Python 3.12.
   - **Source code:** `/home/<username>/leftovers-tracker`
   - **Virtualenv:** `/home/<username>/leftovers-tracker/.venv`
   - **Force HTTPS:** on
4. Edit the **WSGI configuration file** (linked from the Web tab) and replace its contents with:
   ```python
   import os, sys
   path = "/home/<username>/leftovers-tracker"
   sys.path.insert(0, path)
   os.environ["SECRET_KEY"] = "<long random string>"   # python3 -c "import secrets; print(secrets.token_hex(32))"
   os.environ["APP_PASSWORD"] = "<your password>"
   os.environ["SESSION_COOKIE_SECURE"] = "1"
   from app import app as application
   ```
5. Click **Reload** on the Web tab. The SQLite database (`leftovers.db`) is created next to the code.

## Using it on your iPhone

- Open the site in Safari, log in, then tap Share and choose **Add to Home Screen**.
- **Print labels:** on the Labels screen, choose *Avery 5160 sheet* or *Label printer (62 × 29 mm)*.
  To change the label printer size, edit `ROLL_SIZE` in `labels.py` (for example, Dymo 30252 is 89 × 28 mm).
- **Scan:** use the app's **Scan label** button, or point the iPhone **Camera app** at a label. Each QR
  code holds a link (`/l/LO-0001`), so the Camera app opens the right screen directly.
- **Voice:** tap 🎤 next to the name field. If Safari's speech recognition is unavailable, as can
  happen in home-screen mode, use the mic key on the iOS keyboard.
- **Lost or smudged label:** reprint that code on the Labels screen (for example, `LO-0007`).

Labels print with the address of the site that generated them, so print them from the deployed site,
not from localhost.
