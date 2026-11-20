# Later integration — Autonomous CFO

Infrastructure already running:
- Qwen3-8B via vLLM (`my-first-model`)
- MLflow 3.14.0, experiment `autonomous-cfo-agents`; tested in workspace `sth`
- NeMo Guardrails (`autonomous-cfo-guardrails`), standalone `/v1/guardrail/checks`

## MLflow → FastAPI / LangGraph

- [ ] Add a compatible MLflow Python SDK to backend dependencies (`mlflow[kubernetes]>=3.11`).
- [ ] Configure `MLFLOW_TRACKING_URI`, `MLFLOW_TRACKING_AUTH=kubernetes-namespaced`, and the intended workspace through environment/deployment configuration, **not hardcoded secrets**.
- [ ] Grant a dedicated backend ServiceAccount the minimum MLflow workspace permissions; test certificate trust and connection from inside its pod.
- [ ] Set experiment `autonomous-cfo-agents`; enable `mlflow.langchain.autolog()` for LangGraph. Add `mlflow.openai.autolog()` only where direct OpenAI-compatible client calls should also be traced.
- [ ] Verify an end-to-end trace: agent decision -> financial Python tool -> Qwen response. Check timestamps, errors, tool calls, and workspace visibility.
- [ ] Ensure traces do not expose credentials, personal data, or real customer financial information. Test trace sampling and retention.
- [ ] Validate artifact upload/download separately; current SQLite + local file PVC is a hackathon setup and should not be assumed production-ready.

## NeMo Guardrails → FastAPI

- [ ] Configure a dedicated ServiceAccount and RBAC for the guardrails API. Use internal HTTPS Service DNS or a verified route with trusted CA; keep credentials in OpenShift Secrets.
- [ ] Add an input validation step before calling vLLM: `POST /v1/guardrail/checks` with `model` and `messages`.
- [ ] Continue only on `status=success`; on `status=blocked`, return a user-friendly policy response and do **not** call the model. Define explicit handling of timeouts/errors (fail-closed for high-risk requests).
- [ ] Revisit demo rules: blocking every email/phone number and keywords like `secret` may be overly restrictive for a CFO assistant.
- [ ] If needed, add explicit *output* rails and test them; current ConfigMap only configures *input* rails.
- [ ] Add tests for safe input, PII, regex keywords, bypass attempts, error handling and cases that should remain allowed.
- [ ] Record guardrail outcome in app logs/MLflow, but avoid logging the sensitive content itself.

## End-to-end demo

- [ ] Show permitted user message -> guardrails success -> LangGraph -> Qwen -> trace in MLflow.
- [ ] Show blocked message -> guardrails blocked -> no Qwen invocation.
- [ ] Ensure money transfers/investments/tax actions always require deterministic backend authorization and explicit user approval. Guardrails do not enforce financial approvals by themselves.
- [ ] Save sanitized sample traces/screenshots before the hackathon environment is deleted.
