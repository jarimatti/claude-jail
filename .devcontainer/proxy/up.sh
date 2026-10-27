#!/bin/bash
# Idempotently start the egress proxy for the jail. Run on the host (devcontainer initializeCommand).
#   claude-jail-net     --internal network: no route out; the jail lives here
#   claude-jail-egress  normal network: only the proxy is attached to it
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
NAME=claude-jail-proxy
IMAGE=docker.io/ubuntu/squid:latest

podman network exists claude-jail-net    || podman network create --internal claude-jail-net >/dev/null
podman network exists claude-jail-egress || podman network create claude-jail-egress >/dev/null

# Recreate so config changes always apply
podman rm -f "$NAME" >/dev/null 2>&1 || true
podman run -d --name "$NAME" --restart=unless-stopped \
  --network claude-jail-net --network claude-jail-egress \
  -v "$DIR/squid.conf:/etc/squid/squid.conf:ro" \
  -v "$DIR/allowed-domains.txt:/etc/squid/allowed-domains.txt:ro" \
  "$IMAGE" >/dev/null
echo "claude-jail-proxy up"
