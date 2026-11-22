#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help || ${1:-} == -h ]]; then
    echo 'Usage: send-demo-investment-email.sh'
    echo 'Send one sample investment opportunity to OWNER_EMAIL using the cfo-ai backend.'
    exit 0
fi
if (( $# != 0 )); then
    echo 'Usage: send-demo-investment-email.sh' >&2
    exit 2
fi

exec oc exec -n cfo-ai deployment/cfo-backend -c backend -- \
    python -m app.notifications.balance_alerts --demo investment
