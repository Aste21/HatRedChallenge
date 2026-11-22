#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo 'Usage: build-openshift.sh {backend|instruments|frontend} [--wait-for-image] [--backend-image IMAGE@sha256:DIGEST]'
}
fail() { echo "Build error: $*" >&2; exit 1; }

component=${1:-}
case "$component" in
    -h|--help) usage; exit 0 ;;
    backend|instruments|frontend) shift ;;
    *) usage >&2; exit 2 ;;
esac
wait_for_image=false
backend_image=''
while (( $# )); do
    case "$1" in
        --wait-for-image) wait_for_image=true; shift ;;
        --backend-image) [[ -n ${2:-} ]] || fail 'Missing backend image'; backend_image=$2; shift 2 ;;
        *) usage >&2; exit 2 ;;
    esac
done

repo=$(cd "$(dirname "$0")/.." && pwd)
registry='image-registry.openshift-image-registry.svc:5000/cfo-ai'
digest_pattern='^sha256:[0-9a-f]{64}$'
if [[ -n $backend_image ]]; then
    [[ $component == instruments && ${backend_image%@*} == "$registry/cfo-backend" &&
       ${backend_image#*@} =~ $digest_pattern ]] || fail 'Expected a pinned cfo-backend image for instruments'
fi

dir="$repo/$component"
case "$component" in
    backend) files=(Dockerfile pyproject.toml); sources=('app/*.py' 'app/knowledge/*/company_knowledge.md') ;;
    frontend) files=(Dockerfile package.json package-lock.json .npmrc tsconfig.json vite.config.ts); sources=(src static) ;;
    instruments) dir="$repo/instrument_recommendation_agent"; files=(requirements.txt); sources=('app/*.py') ;;
esac
scratch=$(mktemp -d "${TMPDIR:-/tmp}/cfo-build.XXXXXXXX")
cleanup() {
    rm -f -- "$scratch/paths" "$scratch/sources.tar.gz" "$scratch/Dockerfile.openshift"
    rmdir "$scratch"
}
trap cleanup EXIT

# Package working-tree files with the same allowlist as the PowerShell build.
git -C "$dir" ls-files -z --cached --others --exclude-standard -- "${sources[@]}" > "$scratch/paths"
while IFS= read -r -d '' file; do
    if [[ -f "$dir/$file" || -L "$dir/$file" ]]; then files+=("$file"); fi
done < "$scratch/paths"
tar_inputs=(-C "$dir" "${files[@]}")
if [[ $component == instruments ]]; then
    if [[ -z $backend_image ]]; then
        digest=$(oc get imagestreamtag cfo-backend:release -n cfo-ai -o 'jsonpath={.image.metadata.name}')
        [[ $digest =~ $digest_pattern ]] || fail 'Build the release backend first or pass --backend-image'
        backend_image="$registry/cfo-backend@$digest"
    fi
    IFS= read -r base < "$dir/Dockerfile.openshift"
    [[ ${base%$'\r'} == "FROM $registry/cfo-backend:release" ]] || fail 'Unexpected instrument base image'
    { printf 'FROM %s\n' "$backend_image"; tail -n +2 "$dir/Dockerfile.openshift"; } > "$scratch/Dockerfile.openshift"
    tar_inputs+=(-C "$scratch" Dockerfile.openshift)
fi
COPYFILE_DISABLE=1 tar -czf "$scratch/sources.tar.gz" "${tar_inputs[@]}"
start=(start-build "cfo-$component" -n cfo-ai "--from-archive=$scratch/sources.tar.gz")
if ! $wait_for_image; then oc "${start[@]}"; exit; fi
build=$(oc "${start[@]}" --wait -o name)
digest=$(oc get "$build" -n cfo-ai -o 'jsonpath={.status.output.to.imageDigest}')
[[ $digest =~ $digest_pattern ]] || fail "Missing image digest for $build"
echo "$build completed" >&2
printf '%s/cfo-%s@%s\n' "$registry" "$component" "$digest"
