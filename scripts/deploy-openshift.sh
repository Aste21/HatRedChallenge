#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo 'Usage: deploy-openshift.sh [--dry-run] [--build-versions BACKEND INSTRUMENTS FRONTEND]'
}
fail() { echo "Deploy error: $*" >&2; exit 1; }

dry_run=false
use_builds=false
while (( $# )); do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --dry-run) dry_run=true; shift ;;
        --build-versions)
            [[ $# -ge 4 ]] || fail 'Supply build numbers in backend, instruments, frontend order'
            for version in "$2" "$3" "$4"; do [[ $version =~ ^[1-9][0-9]*$ ]] || fail "Invalid build number: $version"; done
            versions=("$2" "$3" "$4"); use_builds=true; shift 4 ;;
        *) usage >&2; exit 2 ;;
    esac
done

scripts=$(cd "$(dirname "$0")" && pwd)
manifests="$scripts/../deploy/cfo"
namespace=cfo-ai
registry="image-registry.openshift-image-registry.svc:5000/$namespace"
components=(backend instruments frontend)
server=$(oc whoami --show-server)
identity=$(oc whoami)
echo "Cluster $server | user $identity | project $namespace"

release_image() {
    local component=$1 build="build/cfo-$1-$2" phase target digest result
    result=$(oc get "$build" -n "$namespace" -o 'jsonpath={.status.phase}{" "}{.spec.output.to.name}{" "}{.status.output.to.imageDigest}') || return 1
    read -r phase target digest <<< "$result"
    [[ $phase == Complete && $target == "cfo-$component:release" && $digest =~ ^sha256:[0-9a-f]{64}$ ]] ||
        fail "Invalid release build: $build"
    echo "$registry/cfo-$component@$digest"
}
images=()
if $use_builds; then
    for index in 0 1 2; do
        image=$(release_image "${components[index]}" "${versions[index]}")
        images+=("$image")
    done
fi
if $dry_run; then
    inputs=(create --dry-run=client -o name)
    for name in builds backend instruments frontend access network app-session-template; do
        inputs+=(-f "$manifests/$name.yaml")
    done
    oc "${inputs[@]}"
    exit
fi

project=$(oc get namespace "$namespace" --ignore-not-found -o name)
if [[ -z $project ]]; then
    printf '%s\n' 'apiVersion: v1' 'kind: Namespace' "metadata: {name: $namespace, labels: {opendatahub.io/dashboard: 'true'}}" | oc apply -f -
fi
oc apply -f "$manifests/builds.yaml"
if ! $use_builds; then
    for component in "${components[@]}"; do
        args=("$component" --wait-for-image)
        if [[ $component == instruments ]]; then args+=(--backend-image "${images[0]}"); fi
        echo "Building cfo-$component" >&2
        image=$(bash "$scripts/build-openshift.sh" "${args[@]}")
        images+=("$image")
    done
fi

oc apply -f "$manifests/access.yaml" -f "$manifests/network.yaml"
session=$(oc get secret cfo-app-session -n "$namespace" --ignore-not-found -o name)
if [[ -z $session ]]; then
    if ! oc process --local -f "$manifests/app-session-template.yaml" -o json | oc create -n "$namespace" -f -; then
        # Another deployment may have created it between get and create.
        oc get secret cfo-app-session -n "$namespace" -o name >/dev/null
    fi
fi

scratch=$(mktemp -d "${TMPDIR:-/tmp}/cfo-release.XXXXXXXX")
cleanup() {
    rm -f -- "$scratch/backend.yaml" "$scratch/instruments.yaml" "$scratch/frontend.yaml" "$scratch/kustomization.yaml"
    rmdir "$scratch"
}
trap cleanup EXIT
for component in "${components[@]}"; do cp "$manifests/$component.yaml" "$scratch/"; done
# Match the PowerShell hash across LF and CRLF checkouts.
config_hash=$(tr -d '\r' < "$scratch/backend.yaml" | openssl dgst -sha256 | awk '{print toupper($NF)}')
[[ $config_hash =~ ^[A-F0-9]{64}$ ]] || fail 'Could not hash backend.yaml'

apply_components() {
    local file image
    {
        printf '%s\n' 'apiVersion: kustomize.config.k8s.io/v1beta1' 'kind: Kustomization' 'resources:'
        for file in "$@"; do printf '  - %s.yaml\n' "$file"; done
        printf 'commonAnnotations:\n  cfo/config-sha256: "%s"\nimages:\n' "$config_hash"
        for image in "${images[@]}"; do
            printf '  - name: %s\n    digest: %s\n' "${image%@*}" "${image#*@}"
        done
    } > "$scratch/kustomization.yaml"
    oc apply -n "$namespace" -k "$scratch"
}
apply_components backend instruments
for component in backend instruments; do oc rollout status "deployment/cfo-$component" -n "$namespace" --timeout=10m; done
apply_components frontend
oc rollout status deployment/cfo-frontend -n "$namespace" --timeout=10m
oc wait '--for=jsonpath={.status.ingress[0].conditions[0].status}=True' route/autonomous-cfo -n "$namespace" --timeout=2m
host=$(oc get route autonomous-cfo -n "$namespace" -o 'jsonpath={.spec.host}')
echo "CFO application: https://$host/"
oc exec -i -n "$namespace" deploy/cfo-backend -- python - < "$scripts/evaluate-cfo.py"
echo 'CFO deployment and acceptance completed.'
