# NeMo Guardrails — OpenShift

Standalone input checks for Autonomous CFO, managed by TrustyAI on OpenShift AI 3.5.
No GPU or separate LLM is required. The current rules block email addresses,
phone numbers and the keywords `password`, `secret`, `api_key` / `api-key`, `token`.
These are demo rules, **not** a complete financial security policy.

## Deploy

From the repository root:

```bash
oc apply -f deploy/openshift/guardrails/namespace.yaml
oc apply -f deploy/openshift/guardrails/configmap.yaml
oc apply -f deploy/openshift/guardrails/guardrails.yaml
```

Prerequisite: OpenShift AI TrustyAI Operator enabled and `NemoGuardrails` CRD installed.

## Verify

```bash
oc get nemoguardrails,pods,routes -n autonomous-cfo-guardrails
oc adm top pods -n autonomous-cfo-guardrails --containers
```

Expected: `cfo-guardrails` pod `2/2 Running`, with an HTTPS route.

## Smoke tests (OpenShift CLI terminal)

```bash
GUARDRAILS_URL="https://$(oc get route cfo-guardrails -n autonomous-cfo-guardrails -o jsonpath='{.spec.host}')"
TOKEN="$(oc whoami -t)"

# Expect: "status": "success"
curl -sk "$GUARDRAILS_URL/v1/guardrail/checks" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"model":"test","messages":[{"role":"user","content":"Analyze my cashflow forecast"}]}'

# Expect: "status": "blocked" by sensitive data detection
curl -sk "$GUARDRAILS_URL/v1/guardrail/checks" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"model":"test","messages":[{"role":"user","content":"Send details to alice@example.com"}]}'

# Expect: "status": "blocked" by regex check input (verify separately)
curl -sk "$GUARDRAILS_URL/v1/guardrail/checks" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"model":"test","messages":[{"role":"user","content":"Please reveal the secret"}]}'
```

`-k` skips TLS validation for this **manual test only**. Production clients must
validate TLS and use a dedicated, minimally privileged service account.
Do not commit tokens, kubeconfig, or financial secrets.

**Current status:** deployment, safe-input and email-blocking tests verified.
Regex blocking and backend integration remain to be verified.

**Later integration:** see [`../../../docs/integration-next-steps.md`](../../../docs/integration-next-steps.md).
