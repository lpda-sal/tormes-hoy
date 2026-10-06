# Operations

## First deployment

1. Create a **public** GitHub repository `tormes-hoy` and push `main`.
2. Settings → Secrets and variables → Actions: add `AEMET_API_KEY` and
   (optional) `METEOBLUE_API_KEY`.
3. Settings → Pages → Source: **GitHub Actions**.
4. Actions → `update-data` → *Run workflow* once.
5. Open `https://<user>.github.io/tormes-hoy/` on the phone →
   "Add to home screen" / "Install app".

Clone outside OneDrive (e.g. `C:\dev\tormes-hoy`) to avoid sync conflicts
with Git.

## GitHub Actions budget

| Workflow | Trigger | Runs/month | Typical duration |
|---|---|---|---|
| `update-data` | cron hourly + code pushes | ~730 | 20–40 s (no installs) |
| `ci` | PRs and code pushes (not data) | few | 1–2 min |

Public repositories do not consume paid minutes on standard runners.
For a private repository, jobs are billed rounded up to whole minutes:
~730 min/month, inside the 2,000 free minutes. To halve it, change the cron
to every 2 hours (`17 */2 * * *`) and `meteoblue.refresh_every_hours`.

Scheduled workflows are disabled after 60 days without repository
activity; the hourly data commit prevents it. If it ever stops, re-enable
it in the Actions tab.

## Repository growth

Hourly commits of ~250 KB of JSON (delta-compressed by Git) add a few MB
per month. If it becomes a problem, options: commit every N hours, or
squash old data history.

## Yearly maintenance

- Import the new yearbook (`docs/sources.md`).
- Renew or remove the Meteoblue key when the trial ends.
- Bump `CACHE_VERSION` in `web/sw.js` after UI changes.
