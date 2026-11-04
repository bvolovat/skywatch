# SkyWatch

A small two-service weather app (Flask frontend + backend API calling [Open-Meteo](https://open-meteo.com)),
deployed to a local K3s cluster through GitHub Actions and ArgoCD.

> Work in progress. Full architecture, setup-from-scratch steps and design decisions will be added here.

## Repository layout

```
apps/backend/    # HTTP API: GET /api/weather?city=..., /healthz, /readyz
apps/frontend/   # Flask web page with a city form, calls the backend
charts/skywatch/ # Helm chart for the whole app
infra/           # Multipass VM scripts + Ansible roles for K3s
.github/         # CI pipeline
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

## Helm chart (`charts/skywatch`)

One chart deploys the whole app:

| Resource | Details |
|----------|---------|
| `skywatch-frontend` Deployment + Service | 1 replica, `NodePort 30080`, reachable from the host at `http://<node-ip>:30080` |
| `skywatch-backend` Deployment + Service | 2 replicas, internal `ClusterIP` on port 8000, spread across the two workers |
| `skywatch-backend` PodDisruptionBudget | `minAvailable: 1`, so a node drain never takes both backend pods down |
| ConfigMaps (one per service) | All runtime config from `values.yaml`; `BACKEND_URL` is built from the backend Service name |

Design notes:
- **Config, not images**: every setting comes from `values.yaml` through a ConfigMap (`envFrom`). A `checksum/config`
  annotation rolls the pods when the ConfigMap changes, since env vars are only read at start.
- **Probes**: backend liveness `/healthz`, readiness `/readyz` (which deliberately does not call Open-Meteo, so an
  external outage does not remove every pod from the Service); frontend uses `/healthz`.
- **Resources**: requests and limits on every container.
- **Hardening**: non-root UID 10001, read-only root filesystem (with an `emptyDir` on `/tmp` for gunicorn),
  all capabilities dropped, `RuntimeDefault` seccomp.
- **Image tags** are full commit SHAs written by CI; `pullPolicy: IfNotPresent` is safe because SHA tags are immutable.

## CI (`.github/workflows/ci.yaml`)

| Job | Runs on | What it does |
|-----|---------|--------------|
| `lint-test` | push + PR | `ruff` lint/format, `pytest` for both services, `hadolint` for both Dockerfiles, `helm lint` |
| `build` (matrix: backend, frontend) | push + PR | Multi-arch build (`linux/amd64` + `linux/arm64` via QEMU); on `main` pushes to `ghcr.io/<owner>/skywatch-<service>:<commit-sha>` |
| `update-tags` | push to `main` only | Writes the new SHA into `charts/skywatch/values.yaml` with `yq` and pushes a bot commit |

- **No trigger loop**: the tag commit is pushed with `GITHUB_TOKEN`, and GitHub never starts workflow runs from
  `GITHUB_TOKEN` pushes. The commit message also carries `[skip ci]` as a second guard.
- **Caching**: pip cache in `setup-python`; Docker layer cache in the GitHub Actions cache (`type=gha`), one scope per
  service.
- **Races**: `concurrency` cancels a superseded run on the same branch, and the bump job rebases on `main` before pushing.
- **arm64**: the Multipass VMs on Apple Silicon are arm64 while GitHub's default runners are amd64, so images are built
  for both architectures.

One-time setup after the first successful run: in GitHub, open each package (`skywatch-backend`, `skywatch-frontend`)
→ Package settings → Change visibility → **Public**, so the cluster can pull without credentials.

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
