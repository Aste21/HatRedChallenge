# Frontend

## Open in Dev Spaces

From the repository root on the `ui-dashboard` branch:

```sh
git pull --ff-only origin ui-dashboard
cd frontend
npm ci
npm run workspace
```

Keep the terminal running. In Explorer, expand **Endpoints** and open **frontend** on port **5173** in a new tab. An already running workspace can also offer **Open in New Tab** when it detects the port. A Git pull updates the checkout; an existing workspace can keep its previous devfile configuration. If neither option appears, start a workspace from the `ui-dashboard` branch so Dev Spaces reads its endpoint declaration.

If Vite reports a blocked host, stop the preview with Ctrl+C, set `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS` to the exact hostname from the generated frontend URL (without the scheme or path), then run `npm run workspace` again.

For later updates, stop the preview, return to the repository root and repeat the commands. If Git reports that local edits would be overwritten, use `git status --short` to identify the file and save your edits before pulling. For the earlier starter page, `git stash push -m "Save Dev Spaces starter page" -- frontend/src/routes/+page.svelte` preserves that file in the stash.

## Data and integration

| Screen | Current implementation |
| --- | --- |
| Cashflow | Daily balances and monthly totals from the 2025 CSV. The forecast tab shows a 7-, 14- or 31-day fixed-cost scenario until the forecasting service is available. |
| Proposals | Two illustrative proposals. Approve or decline locally. An approval records a simulated decision in browser storage. Connecting the team's approval API will enable shared decisions and backend notifications. |
| Business news | The server reads `GET /articles?status=accepted` from the team's news service. Set `NEWS_API_URL` to the base URL reachable from the workspace before starting the preview. |
| Chat | Prepared answers about the statement, payments and proposals. The live chat backend can replace the answer handler in `src/routes/assistant/+page.svelte`. |

Run `python scripts/statement.py` from this directory to regenerate the aggregate fixture from the CSV. Amounts are stored in euro cents. For local development use `npm run dev`. Run `npm run check` and `npm run build` before sharing changes.
