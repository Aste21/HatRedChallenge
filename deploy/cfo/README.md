# Autonomous CFO on OpenShift

The CFO frontend, FastAPI backend and instrument agent run in `cfo-ai`. The backend uses the existing news and forecast services in `sth`. Qwen runs in `my-first-model`. NeMo validates input before chat inference and before the instrument agent drafts its notification. The main app stores conversations and simulated decisions on the `cfo-data` PVC.

## Build and deploy

From a checkout of this repository, log in with `oc login` to the hackathon cluster. Use PowerShell with Git, tar.exe and oc on PATH. The account needs to deploy in `cfo-ai` and apply the roles and bindings in `deploy/cfo/access.yaml`. The deployment uses the existing Qwen, NeMo, MLflow and `sth` services, the internal image registry and the `gp3-csi` storage class.

```powershell
.\scripts\deploy-openshift.ps1
```

The script prints the cluster and identity, creates the CFO namespace if needed, and builds the current local sources. The instrument image inherits the exact backend image from the same invocation. After all builds succeed, it applies the manifests, waits for the three deployments and Route, prints the application URL and runs the acceptance check below. Its nonzero exit status signals a failed command or evaluation. A failed evaluation leaves the deployment available for inspection.

Running the command again updates the CFO deployment and reuses its PVC and OAuth session secret. To check the target and validate the manifests before building, run:

```powershell
.\scripts\deploy-openshift.ps1 -WhatIf
```

## Access and acceptance

Open the `autonomous-cfo` Route and log in with an OpenShift user allowed to get pods in `cfo-ai`. The app represents one shared demo business. The backend and instrument API are internal. Input policy failures return 422, and a temporarily unavailable NeMo service returns 503. The MLflow experiment `autonomous-cfo-agents` is in workspace `cfo-ai`. Traces record decisions, timings and model metadata.

```powershell
Get-Content -Raw scripts/evaluate-cfo.py | oc exec -i -n cfo-ai deploy/cfo-backend -- python -
```

The evaluation uses the deployed dependencies with a temporary SQLite file and SMTP disabled. It records numeric acceptance metrics in MLflow. Use the frontend assistant separately to verify the complete SvelteKit request path.
