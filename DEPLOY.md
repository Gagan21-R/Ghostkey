# Public demo link (Cloudflare quick tunnel from this laptop)

The app runs as a production build on this laptop and is exposed at a temporary `https://…trycloudflare.com` URL.
The link works only while the laptop is on, awake and online, and **a new URL is issued every time the tunnel restarts**.

## Start / restart
1. Production app (frontend :3000 + backend :8000), from `Hackathon/`:
   ```bash
   npm --prefix ghostkey/frontend run prod:all
   ```
   (or the `ghostkey-prod` launch configuration). It rebuilds first (~1 min).
2. Tunnel (in a second terminal). `--protocol http2` is needed on networks that block QUIC/UDP, like the venue Wi-Fi:
   ```bash
   "%LOCALAPPDATA%\ghostkey\tools\cloudflared.exe" tunnel --no-autoupdate --protocol http2 --url http://localhost:3000
   ```
   Copy the `https://….trycloudflare.com` URL it prints and share it.

## Public-mode settings (backend/.env)
- `GHOSTKEY_PUBLIC=1`: the "run backend test suite" button is disabled for visitors (returns 403 and records a SKIPPED report).
- `GHOSTKEY_LOCAL_DOWNLOADS=0`: the "Latest in Downloads" picker is off, so the host's Downloads folder is never exposed. Set it to `1` only for local use.
- `GHOSTKEY_API_TOKEN`: a random internal token, the same value in `frontend/.env.local`. Only the Next.js server sends it. The backend (:8000) is bound to 127.0.0.1 and is not exposed.
- `GHOSTKEY_DB`: the live SQLite database is in `%LOCALAPPDATA%\ghostkey\ghostkey.db`, outside OneDrive, because OneDrive sync can corrupt a SQLite file while it is being written.

## Things to know
- Anyone with the link can run live checks, and each one spends DetectifAI credits (shown on the dashboard).
- Keep the laptop plugged in with sleep disabled (Windows Settings → System → Power) for the whole demo window.
- Back to development: stop the production app and run `npm --prefix ghostkey/frontend run dev:all`.
