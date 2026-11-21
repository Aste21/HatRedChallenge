# Autonomous CFO on OpenShift

The CFO frontend, FastAPI backend and instrument agent run in `cfo-ai`. The backend uses the existing news and forecast services in `sth`. Qwen runs in `my-first-model`. NeMo validates input before chat inference and before the instrument agent drafts its notification. The main app stores conversations and simulated decisions on the `cfo-data` PVC.

## Build and deploy

From a checkout of this repository, log in with `oc login` to the hackathon cluster. Use PowerShell with Git, tar.exe and oc on PATH. The account needs to deploy in `cfo-ai` and apply the roles and bindings in `deploy/cfo/access.yaml`. The deployment uses the existing Qwen, NeMo, MLflow and `sth` services, the internal image registry and the `gp3-csi` storage class.

```powershell
.\scripts\deploy-openshift.ps1
```

The script prints the cluster and identity, creates the CFO namespace if needed, and builds the current local sources. The instrument image inherits the exact backend image from the same invocation. After all builds succeed, it applies the manifests, waits for the three deployments and Route, prints the application URL and runs the acceptance check below. Its nonzero exit status signals a failed command or evaluation. A failed evaluation leaves the deployment available for inspection.

To deploy existing successful release builds, pass all three build numbers, for example `-BuildVersions @{backend=4; instruments=2; frontend=3}`. Select the three builds you tested together.

Running the command again updates the CFO deployment and reuses its PVC and application session signing secret. To check the target and validate the manifests before building, run:

```powershell
.\scripts\deploy-openshift.ps1 -WhatIf
```

Approval confirmations use the backend-only `smtp-settings` Secret in `cfo-ai`. Set `SMTP_HOST`, `SMTP_PORT` (STARTTLS), `SMTP_USER`, `SMTP_PASSWORD` and `OWNER_EMAIL`. Each new approval sends its confirmation to the owner and an optional blind copy to `APPROVAL_COPY_EMAIL`. The backend records `sent` when SMTP accepts all recipients. Use a delivery-capable SMTP account for a real inbox. Ethereal captures messages in its test mailbox. Without the Secret, confirmations stay in the application outbox. Restart the backend after rotating SMTP settings.

## Access and acceptance

Open the public `autonomous-cfo` Route and use the application login shown on the landing page. The demo account shares business data across its sessions. This release uses `/data/cfocus-demo.sqlite3` so the original access-controlled database is preserved on the same PVC. The backend and instrument API are internal. Input policy failures return 422, and a temporarily unavailable NeMo service returns 503. The MLflow experiment `autonomous-cfo-agents` is in workspace `cfo-ai`. Traces record decisions, timings and model metadata.

```powershell
Get-Content -Raw scripts/evaluate-cfo.py | oc exec -i -n cfo-ai deploy/cfo-backend -- python -
```

The evaluation uses the deployed dependencies with a temporary SQLite file and SMTP disabled. It records numeric acceptance metrics in MLflow. Use the frontend assistant separately to verify the complete SvelteKit request path.
