# Autonomous CFO on OpenShift

The CFO frontend, FastAPI backend and instrument agent run in `cfo-ai`. The backend uses the existing news and forecast services in `sth`. Qwen runs in `my-first-model`. NeMo validates input before chat inference and before the instrument agent drafts its notification. The main app stores conversations and simulated decisions on the `cfo-data` PVC.

## Build and deploy

From a checkout of this repository, log in with `oc login` to the hackathon cluster. On Windows use PowerShell, Git, tar.exe and oc. On macOS use Bash, Git, tar, openssl and the oc CLI on PATH. Builds run on OpenShift, including when launched from an Apple Silicon Mac. The account needs to deploy in `cfo-ai` and apply the roles and bindings in `deploy/cfo/access.yaml`. The deployment uses the existing Qwen, NeMo, MLflow and `sth` services, the internal image registry and the `gp3-csi` storage class.

```powershell
.\scripts\deploy-openshift.ps1
```

On macOS, run the preview first. Use the second command when you are ready to build and deploy the local checkout.

```bash
./scripts/deploy-openshift.sh --dry-run
./scripts/deploy-openshift.sh
```

The script prints the cluster and identity, creates the CFO namespace if needed, and builds the current local sources. The instrument image inherits the exact backend image from the same invocation. After all builds succeed, it applies the manifests, waits for the three deployments and Route, prints the application URL and runs the acceptance check below. Its nonzero exit status signals a failed command or evaluation. A failed evaluation leaves the deployment available for inspection.

To build an individual image on macOS, run `./scripts/build-openshift.sh frontend --wait-for-image`. The PowerShell equivalent is `.\scripts\build-openshift.ps1 -Component frontend -WaitForImage`. Valid components are `backend`, `instruments` and `frontend`. This uploads a binary build to the existing BuildConfig. Workloads keep their deployed digests. The optional wait prints the new image reference. A standalone instruments build pins the current `cfo-backend:release` digest, or accepts a specific one via `--backend-image` / `-BackendImage`.

To reuse tested images, pass three completed release build numbers. For example, the demo configuration verified for this release is backend **7**, instruments **2**, frontend **4**. On macOS use `./scripts/deploy-openshift.sh --build-versions 7 2 4`. On Windows use `.\scripts\deploy-openshift.ps1 -BuildVersions @{backend=7; instruments=2; frontend=4}`. To include new local changes, run the full deployment instead of selecting older builds.

Running the command again updates the CFO deployment and reuses its PVC and application session signing secret. Both platforms hash the same LF-normalized backend manifest. The first deployment after upgrading from an older Windows checkout can roll pods once to update that annotation. To check the target and validate the manifests before building, run:

```powershell
.\scripts\deploy-openshift.ps1 -WhatIf
```

Approval confirmations use the backend-only `smtp-settings` Secret in `cfo-ai`. Set `SMTP_HOST`, `SMTP_PORT` (STARTTLS), `SMTP_USER`, `SMTP_PASSWORD` and `OWNER_EMAIL`. Each new approval sends its confirmation to the owner and an optional blind copy to `APPROVAL_COPY_EMAIL`. The backend records `sent` when SMTP accepts all recipients. Use a delivery-capable SMTP account for a real inbox. Ethereal captures messages in its test mailbox. Without the Secret, confirmations stay in the application outbox. Restart the backend after rotating SMTP settings.

## Reopen a proposal before a demo

With `oc` logged in, run this from the repository root:

```powershell
.\scripts\reset-demo-approval.ps1
```

On macOS or Linux, preview the approved proposals and run the reset when ready:

```bash
./scripts/reset-demo-approval.sh --preview
./scripts/reset-demo-approval.sh
```

If several approvals are listed, select one with `./scripts/reset-demo-approval.sh --proposal-id <id>`.

Refresh **Proposals** in CFOcus and approve an offer again. The command resets one approved Amalfi decision, its simulated transaction and its in-app approval notification. It saves those records on the demo PVC first. In PowerShell, use `-Preview` to list their IDs and `-ProposalId <id>` to select one. Email is sent on the next approval.

## Access and acceptance

Open the public `autonomous-cfo` Route and use the application login shown on the landing page. The demo account shares business data across its sessions. This release uses `/data/cfocus-demo.sqlite3` so the original access-controlled database is preserved on the same PVC. The backend and instrument API are internal. Input policy failures return 422, and a temporarily unavailable NeMo service returns 503. The MLflow experiment `autonomous-cfo-agents` is in workspace `cfo-ai`. Traces record decisions, timings and model metadata.

```powershell
Get-Content -Raw scripts/evaluate-cfo.py | oc exec -i -n cfo-ai deploy/cfo-backend -- python -
```

The evaluation uses the deployed dependencies with a temporary SQLite file and SMTP disabled. It records numeric acceptance metrics in MLflow. Use the frontend assistant separately to verify the complete SvelteKit request path.
