# Qwen3-8B — OpenShift AI

Qwen3-8B FP8 served by vLLM on one NVIDIA L4 GPU, with OpenAI-compatible API, tool calling, and Qwen3 thinking disabled by default.

- Namespace: `my-first-model`
- InferenceService: `qwen3-8b`
- Model: `oci://registry.redhat.io/rhelai1/modelcar-qwen3-8b-fp8-dynamic:1.5`
- GPU: 1; requests: 4 CPU / 12 GiB RAM; limits: 8 CPU / 16 GiB RAM

## Verify existing model

```bash
oc get isvc qwen3-8b -n my-first-model
oc get pods -n my-first-model
oc get isvc qwen3-8b -n my-first-model -o jsonpath='{.status.url}{"\n"}'
```

## Deploy / restore

Prerequisites: OpenShift AI KServe/vLLM serving runtime, GPU operator, accessible model OCI registry and permissions to deploy models.

**Before applying:** compare the manifest with the running model, especially `spec.predictor.model.runtime`, labels, annotations and any additional pod scheduling settings:

```bash
oc get isvc qwen3-8b -n my-first-model -o yaml
oc get isvc qwen3-8b -n my-first-model -o jsonpath='{.spec.predictor.model.runtime}{"\n"}'
oc apply --dry-run=server -f deploy/openshift/models/qwen3-8b.yaml
oc diff -f deploy/openshift/models/qwen3-8b.yaml
```

The manifest reflects the known working configuration, but is **not a verified full export** of the running resource. Add the actual ServingRuntime name and any necessary settings found in the live spec before restoring it. Applying changes to the current model may restart it. On a new cluster, configure the matching ServingRuntime first.

When intentionally deploying:

```bash
oc apply -f deploy/openshift/models/qwen3-8b.yaml
oc get isvc qwen3-8b -n my-first-model -w
```

## Access

Get the URL from `status.url`, append `/v1`. Retrieve the model ID from authenticated `GET /v1/models`. Configure the backend using `LLM_BASE_URL`, `LLM_MODEL`, and a token in `LLM_API_KEY` (via OpenShift Secret, **never in Git**).
