# MLflow — OpenShift

MLflow is used for experiment tracking and tracing AI agents in Autonomous CFO.

**Configuration:** MLflow 3.14.0, SQLite, 10 GiB PVC (`gp3-csi`), 1 replica, no GPU.

## Deployment

Run from the repository root.

**1. Enable the MLflow Operator:**

```bash
oc patch datasciencecluster default-dsc --type=merge \
  -p '{"spec":{"components":{"mlflowoperator":{"managementState":"Managed"}}}}'
```

**2. Verify the operator is ready:**

```bash
oc get datasciencecluster default-dsc \
  -o jsonpath='{.status.conditions[?(@.type=="MLflowOperatorReady")].status}{"\n"}'
```

Expected: `True`.

**3. Deploy MLflow:**

```bash
oc apply -f deploy/openshift/mlflow/instance.yaml
```

## Verification

```bash
oc get mlflow mlflow
oc get pods -n redhat-ods-applications | grep mlflow
oc get pvc -n redhat-ods-applications
```

Expected: `AVAILABLE=True`, `PROGRESSING=False`, server `Running`, PVC `Bound`.

## Python integration

```bash
pip install "mlflow[kubernetes]>=3.11,<3.15"
```

With the tracking URI and Kubernetes authentication configured:

```python
import mlflow

mlflow.set_experiment("autonomous-cfo-agents")
mlflow.langchain.autolog()  # LangGraph tracing
mlflow.openai.autolog()     # vLLM OpenAI-compatible client
```

## Monitoring

```bash
oc adm top pods -n redhat-ods-applications --containers | grep mlflow
oc describe mlflow mlflow
```

## Notes

- MLflow workloads run in `redhat-ods-applications`.
- Experiments and traces are stored on the cluster, **not in Git**.
- Deleting the PVC or cluster may erase the data.
- Local `file://` artifact storage requires separate testing before relying on artifact uploads.
