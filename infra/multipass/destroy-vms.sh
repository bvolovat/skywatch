#!/usr/bin/env bash
# Deletes the SkyWatch VMs and the generated inventory/kubeconfig.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

for name in k3s-cp k3s-w1 k3s-w2; do
  if multipass info "$name" >/dev/null 2>&1; then
    echo ">> deleting $name"
    multipass delete "$name"
  fi
done
multipass purge

rm -f "$REPO_ROOT/infra/ansible/inventory/hosts.ini" "$REPO_ROOT/kubeconfig"
echo ">> done"
