# CFOcus frontend

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
| Cashflow | Daily balances and monthly totals from the 2025 CSV. The Forecast tab shows the 30/60/90-day forecast of the forecasting service (expected balance and likely range) via the backend's `GET /api/forecast`. Without the backend it falls back to an illustrative fixed-cost scenario. |
| Proposals | Loaded from the backend's `GET /api/proposals`, which combines the forecast with the instrument recommendation agent (fixed-term deposits) and adds a credit line when the forecast may go below zero. Approve/Decline calls `POST /api/proposals/{id}/decision`, which records a simulated transaction and a notification. Deposit offers use the same cash, so approving one marks the others as "another option chosen". |
| Business news | The server reads `GET /articles?status=accepted` from the team's news service. Set `NEWS_API_URL` to the base URL reachable from the workspace before starting the preview. |
| Chat | Live answers from the LLM on OpenShift AI, with saved conversations (AI-generated titles) on the Chat page and a floating assistant in the bottom-right corner of every other page. The floating assistant sends the visible text of the current page (plus extra data a page registers with `providePageDetails`) so owners can ask about what they see. The browser calls the SvelteKit server routes `/api/chat` and `/api/conversations`, which forward to the backend. Set `CHAT_API_URL` to the backend base URL (default `http://127.0.0.1:8000`; prefer `127.0.0.1` over `localhost` on Windows, where `localhost` first tries IPv6 and adds ~2 s per call); the same backend also serves the forecast and proposals. The assistant also receives the latest forecast, approved actions and news headlines from the backend. |

Run `python scripts/statement.py` from this directory to regenerate the aggregate fixture from the CSV. Amounts are stored in euro cents. For local development use `npm run dev`. Run `npm run check` and `npm run build` before sharing changes.
