# IoT-Project---Maze-Game

## Live leaderboard on Render

The leaderboard uses three parts:

- `site/` is the static website already hosted by Render.
- `leaderboard_api.py` receives completed game scores and reads them for the website.
- Render Postgres stores score submissions between deploys and restarts.

### Create the database

In Render, choose **New +** → **PostgreSQL**. For scores to remain available long term, choose a paid database plan. Render's free Postgres databases expire after 30 days.

### Create the score API

Choose **New +** → **Web Service**, connect this repository, and use:

| Setting | Value |
|---|---|
| Name | `maze-leaderboard-api` |
| Branch | `main` |
| Root Directory | Leave blank |
| Runtime | Python |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn leaderboard_api:app` |

Add an environment variable named `DATABASE_URL` with the database's **Internal Database URL** from Render. Keep the database and web service in the same Render region so the internal address works.

The API URL should then be `https://maze-leaderboard-api.onrender.com`. If Render gives your service a different URL, update `site/leaderboard-config.js` and the default URL near the top of `Maze-Game.py` to match it.

### Publish the connected website and game

Push the changed files to GitHub's `main` branch. The existing static site will redeploy automatically and display saved scores. The Python game source submits its player's name and score when the player completes the final level. The existing packaged `.exe` does not contain this change. To create an updated one on Windows, install the game build dependencies and rebuild it:

```powershell
python -m pip install pygame requests pyinstaller
python -m PyInstaller Maze-Game.spec
```

Run the resulting `dist/Maze-Game.exe`. It uses the API URL configured near the top of `Maze-Game.py` by default. To use a different API URL, set the `LEADERBOARD_API_URL` environment variable before launching it.

The API stores completed runs and shows each player's best score. The current API accepts public submissions without an account, so scores are not protected against tampering.
