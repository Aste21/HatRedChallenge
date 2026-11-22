# Autonomous CFO — Infrastructure context

Updated: 2026-11-21. Historical observations only: verify everything against the live repo and cluster.

## Hackathon goal

Build an explainable, agentic CFO assistant for SMEs on Red Hat OpenShift AI. Complete at least one end-to-end financial workflow (prefer liquidity/cash-flow forecasting): input data → analysis → recommendation → user interaction and approval → simulated action. Clearly distinguish analysis, recommendations, approval requirements, and simulated vs. permitted execution. Hard requirements: run the app on the provided OpenShift cluster and use a model served by OpenShift AI. Optional bonuses include vLLM, llm-d, Models-as-a-Service (MaaS) gateway, MLflow, NeMo Guardrails, OGX/MCP. Main product quality and working end-to-end demo take priority over bonuses.

## Application (verify in repo)

- Frontend: SvelteKit.
- Backend: FastAPI (Python) and LangGraph agents; Python performs deterministic financial calculations, LLM explains/recommends, actions require approvals.
- Example/demo SME: pizzeria; demo/simulated finance data.
- Some components/services may be developed independently. Inspect actual usage of LLM clients and model endpoints; do not assume every service uses Qwen already.
- Existing source of truth: CLAUDE.md if present and actual implementation in repository.

## OpenShift baseline (verify live with oc)

- Single-node OpenShift 4.20.46; Red Hat OpenShift AI 3.5.3.
- ~32 vCPU, ~122 GiB RAM, one NVIDIA L4 GPU (24 GB VRAM). Do not assume GPU sharing.
- Namespace `my-first-model`: existing `InferenceService/qwen3-8b` via vLLM, Qwen3-8B FP8 ModelCar, one GPU; OpenAI-compatible API and tool calling previously tested. Model has `--max-model-len=32768`, `--gpu-memory-utilization=0.90`, Hermes tool-call parser, reasoning parser `qwen3`; RHOAI authentication enabled. Preserve this working model.
- MLflow v3.14.0: server in `redhat-ods-applications`; tracking and trace smoke tests previously passed. Backend integration pending.
- NeMo Guardrails through TrustyAI: namespace `autonomous-cfo-guardrails`; standalone PII/regex checks previously returned `success` on normal text and `blocked` on an email. No current connection to Qwen or backend.
- Historically `modelsAsAService` was Removed and Red Hat Connectivity Link/Kuadrant was not installed; `LLMInferenceService` reported missing dependencies. Re-check: the live environment may have changed.
- GPU is fully allocated to existing Qwen deployment; no plan to run a second GPU LLM.

## Current decision

Evaluate **vLLM (existing baseline)**, **llm-d**, and **OpenShift AI Model Gateway / Models-as-a-Service**. Determine if they can provide a meaningful demo feature, while minimizing disruption and resource use. Do not treat Model Gateway and llm-d as synonyms. Investigate if MaaS can expose the existing vLLM `InferenceService` or requires migration to `LLMInferenceService`. Do not make any change to the live cluster during analysis.

## Security and constraints

- Do not read, print, copy, or commit credential values, kubeconfigs, Secret data, personal finance records, or tokens.
- All oc commands must be read-only during analysis: `get`, `describe`, `api-resources`, `explain`, `auth can-i`, etc. No `patch`, `apply`, `delete`, `scale`, or restarts.
- Current `oc` identity may be cluster-admin: treat the cluster as production-critical for the hackathon.
- Do not add original challenge PDFs marked for business use only to a public repository; use user-authorized local copies or a permitted summary.
