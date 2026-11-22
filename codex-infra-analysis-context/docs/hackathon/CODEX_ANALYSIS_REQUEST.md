# Codex request — Infrastructure feasibility analysis

Act as a senior OpenShift AI platform architect reviewing our **existing** Autonomous CFO hackathon project.

## Sources to inspect first

1. Read `docs/hackathon/INFRA_CONTEXT.md` and `CLAUDE.md` if present.
2. Inspect the current repository: frontend/backend/agent architecture, model clients, inference endpoints, manifests, namespace/RBAC settings, and deployment scripts. Do not assume a component exists because a document claims it does.
3. If I provided local copies of the hackathon Challenge Card, Red Hat Challenge, or OpenShift AI Survival Guide, inspect them and distinguish hard requirements from optional bonuses. If they are inaccessible, call this out; do not invent requirements.
4. Use `oc` only for **read-only discovery** of the live cluster: versions; InferenceService and actual model args; GPU allocation and node resources; DataScienceCluster component statuses; operator/CRD readiness; Gateway API, Kuadrant/Connectivity Link, MaaS, and llm-d prerequisites; namespaces, Services and routes. Avoid Secret values and tokens.
5. Review official Red Hat OpenShift AI **3.5** docs, distinguishing actual confirmed compatibility with our 4.20 cluster from hypothetical possibilities.

## Questions to answer

- What does our existing vLLM `InferenceService/qwen3-8b` already provide, and what is missing for the end-to-end Autonomous CFO demo?
- What benefit would **llm-d** bring on a *single-node, single-GPU* cluster? Does it require replacing or migrating the existing InferenceService? Are prerequisites installed? Is the benefit demonstrable?
- What would **OpenShift AI Model Gateway / MaaS** add (API-key governance, subscriptions, usage limits, authentication)? Can it work with our **existing** vLLM endpoint, or would migration to `LLMInferenceService` be required? What precise resources/operators are needed?
- Which components are actually compatible with each other, and which approaches risk interrupting Qwen, consuming the only GPU, or increasing latency?
- Can we prove a useful bonus without integrating into the entire application yet? What is the smallest reversible proof of concept?
- Does any of the above conflict with current LangGraph / FastAPI architecture, MLflow tracing or NeMo checks?

## Required deliverable (in Polish)

1. **Current state** — verified from repository and live cluster, with relevant file paths, resource names, and commands.
2. **Gap analysis** against hard hackathon requirements and selected bonus objectives.
3. **Comparison table** with options:
   A. Keep current vLLM unchanged;
   B. Add MaaS gateway;
   C. Adopt llm-d;
   D. Combine llm-d and MaaS only if technically supported.
   Rate implementation effort, extra infrastructure, GPU/RAM cost, risks, demo value, benefit and realistic completion likelihood.
4. **Architecture diagrams** (Mermaid) for the baseline and each realistic alternative.
5. **Recommended plan** with phases, concrete checks, dependencies, minimal validation, rollback and a clear stop/go criterion for each phase.
6. **Uncertainties** — clearly label verified facts, source-based claims, and hypotheses needing confirmation.

## Restrictions

This is analysis only. **Do not create/modify files, apply manifests, patch operators, scale services, delete resources, or restart Qwen.** Ask before any change. Do not expose secrets. Do not recommend adding a second GPU-consuming model without proving that resources exist. Prioritize a fully working end-to-end liquidity demo over bonus-chasing. Summarize findings to me before suggesting implementation.
