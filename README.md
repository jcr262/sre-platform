A personal site-reliability lab. I run a three-tier web app on a Kubernetes cluster I built
and operate myself, then inject failures, measure what happens, and write post-mortems.

- Sprint 1: app containerized with Docker Compose, data persisted across restarts
- Sprint 2: deployed to a 3-node k3s cluster with Ingress, Secrets and health probes;
  node-failure test measured end to end (61 s to NotReady, 5 min to eviction)
- Next: Prometheus and Grafana, SLOs with burn-rate alerts, stateful recovery,
  cluster upgrades, centralized logging
