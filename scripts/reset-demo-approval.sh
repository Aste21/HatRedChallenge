#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo 'Usage: reset-demo-approval.sh [--preview] [--proposal-id ID]'
}

mode=reset
proposal_id=''
while (( $# )); do
    case "$1" in
        --preview) mode=preview; shift ;;
        --proposal-id)
            if [[ -n $proposal_id || -z ${2:-} || $2 == -* ]]; then usage >&2; exit 2; fi
            proposal_id=$2
            shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

scripts=$(cd "$(dirname "$0")" && pwd)
args=(exec -i -n cfo-ai deployment/cfo-backend -c backend -- python - "$mode")
if [[ -n $proposal_id ]]; then args+=("$proposal_id"); fi
exec oc "${args[@]}" < "$scripts/reset-demo-approval.py"
