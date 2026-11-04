# SkyWatch

A small two-service weather app (Flask frontend + backend API calling [Open-Meteo](https://open-meteo.com)),
deployed to a local K3s cluster through GitHub Actions and ArgoCD.

> Work in progress. Full architecture, setup-from-scratch steps and design decisions will be added here.

## Repository layout

```
apps/backend/    # HTTP API: GET /api/weather?city=..., /healthz, /readyz
apps/frontend/   # Flask web page with a city form, calls the backend
```

## Cluster provisioning (Path A: Multipass + Ansible + K3s)

Prerequisites on the host (macOS): `brew install --cask multipass` and `brew install ansible kubectl`.

```bash
# 1. Create 3 Ubuntu VMs (1 control plane + 2 workers) and generate the Ansible inventory
./infra/multipass/create-vms.sh

# 2. Install K3s (pinned version) on the control plane and join the workers
cd infra/ansible && ansible-playbook site.yml && cd -

# 3. Use the cluster from the host
export KUBECONFIG=$PWD/kubeconfig
kubectl get nodes -o wide
```

| VM       | Role          | CPU | RAM    | Disk |
|----------|---------------|-----|--------|------|
| `k3s-cp` | control plane | 2   | 1.5 GB | 10G  |
| `k3s-w1` | worker        | 2   | 2.5 GB | 15G  |
| `k3s-w2` | worker        | 2   | 2.5 GB | 15G  |

Design notes:
- **Pinned K3s**: `k3s_version` in `infra/ansible/group_vars/k3s_cluster.yml`. The install script is fetched from the same
  git tag, so the installer is pinned too. Bumping the version and re-running the playbook performs an upgrade.
- **Idempotent**: each role reads `k3s --version` first and only runs the installer when K3s is missing or on a different
  version. Config lives in `/etc/rancher/k3s/config.yaml` (templated); a change there triggers a restart via a handler.
  Re-running the playbook on a healthy cluster reports `changed=0`.
- **No workloads on the control plane**: the server is started with the taint
  `node-role.kubernetes.io/control-plane:NoSchedule`; workers get the `node-role.kubernetes.io/worker=true` label from the control plane
  (a kubelet is not allowed to set `node-role` labels on itself).
- **Secrets**: the join token is read from the server at run time and kept in memory (`no_log`); it is never written to
  the repo. The generated `kubeconfig` and inventory are git-ignored.

Tear down: `./infra/multipass/destroy-vms.sh`

## Running the services locally (without Kubernetes)

```bash
docker build -t skywatch-backend:dev  apps/backend
docker build -t skywatch-frontend:dev apps/frontend
docker network create skywatch
docker run -d --rm --name backend  --network skywatch skywatch-backend:dev
docker run -d --rm --name frontend --network skywatch -p 8080:8080 \
  -e BACKEND_URL=http://backend:8000 skywatch-frontend:dev
open http://localhost:8080
```

## Configuration

| Service  | Variable               | Default                                          |
|----------|------------------------|--------------------------------------------------|
| backend  | `PORT`                 | `8000`                                           |
| backend  | `GEOCODING_URL`        | `https://geocoding-api.open-meteo.com/v1/search` |
| backend  | `FORECAST_URL`         | `https://api.open-meteo.com/v1/forecast`         |
| backend  | `HTTP_TIMEOUT_SECONDS` | `5`                                              |
| frontend | `PORT`                 | `8080`                                           |
| frontend | `BACKEND_URL`          | `http://localhost:8000`                          |
| frontend | `HTTP_TIMEOUT_SECONDS` | `10`                                             |
| both     | `LOG_LEVEL`            | `INFO`                                           |
| both     | `GUNICORN_WORKERS`     | `2`                                              |

## Lint and tests

```bash
pip install ruff pytest flask requests
ruff check . && ruff format --check .
(cd apps/backend && pytest -q) && (cd apps/frontend && pytest -q)
```
