# Autonomous CFO — instructions for coding agents

- This is a single-node OpenShift AI hackathon environment with one NVIDIA L4 GPU.
- Read `docs/hackathon/INFRA_CONTEXT.md` and the repository's existing architecture documentation before proposing infrastructure changes.
- Working services (Qwen3-8B, MLflow, NeMo Guardrails) must not be restarted, replaced or changed without explicit approval.
- Use read-only `oc` commands for inspection; treat current cluster-admin access as high risk.
- Never print or commit credentials, kubeconfigs, Secret values or financial data.
- Save approved reusable manifests under `deploy/openshift/`; verify actual CRDs with `oc explain` before creating manifests.
- Separate confirmed observations from proposals. Prefer fully working product requirements over optional bonuses.
