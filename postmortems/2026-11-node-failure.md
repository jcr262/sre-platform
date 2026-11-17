# Incident: node w1 failure

**Date:** 2026-11-16
**Environment:** k3s lab on Multipass — cp (server), w1, w2 (agents), v1.36.3+k3s1
**Trigger:** deliberate fault injection — `multipass stop w1`
**Author:** Jorge Chavarria

## Impact

No user-visible impact. The Ingress returned HTTP 200 for the whole window.

Two of five pods were lost (1x api, 1x web, both on w1). The surviving replicas
on w2 absorbed all traffic. Postgres was unaffected because it happened to be
scheduled on w2.

That last sentence is the real finding: it was luck, not design. Postgres runs as
a single replica with no persistent volume. Had it been on w1, the application
would have been down for at least 5 minutes and all stored scores would have been
lost permanently, with no automatic recovery.

## Timeline

| Time | Event | Delta from trigger |
|---|---|---|
| 22:24:44 | `multipass stop w1` | — |
| 22:25:45 | Control plane marks w1 NotReady | +1m01s |
| 22:30:51 | Pods on w1 marked Terminating; replacements created on cp | +6m07s |
| 22:30:51 | New pods Running and Ready (api 10.42.0.62, web 10.42.0.63) | +6m07s |
| ~22:50 | `multipass start w1`; node back to Ready | seconds after start |

Time from node loss to full replica count restored: **6m07s**.
Time from NotReady to eviction: **5m06s**.

## What I expected

Before injecting the fault:
- The node would be marked NotReady within about a minute.
- Pods would be rescheduled after roughly 5 minutes, based on the
  `tolerationSeconds: 300` I had seen in `kubectl describe pod`.

Before bringing the node back:
1. The Terminating pods would disappear — correct.
2. The pods would NOT move back to w1 — correct.
3. The node would take about 5 minutes to return to Ready — wrong.

## What actually happened

The first two phases matched. The 5m06s to eviction confirmed the toleration.

The return did not. w1 was Ready within seconds of `multipass start`, not minutes.

Two things happened that were not predicted at all:

1. The replacement pods were scheduled onto **cp**, the control plane node.
2. The Terminating pods stayed Terminating for the entire time the node was down.

## Why the difference

**The 1m01s to NotReady** is consistent with the controller manager's
node-monitor-grace-period (40-50s by default) plus the gap since w1's last
successful heartbeat. The control plane does not detect a dead node immediately;
it waits for heartbeats to stop arriving for a configured period.

**The 5m06s to eviction** is `node.kubernetes.io/not-ready:NoExecute` with
`tolerationSeconds: 300`, which Kubernetes adds to every pod automatically. It
exists so a node that blips does not trigger a cluster-wide reshuffle.

**The asymmetry on the way back** is the real lesson. The 300s toleration governs
eviction only. Nothing equivalent governs the return: the VM boots, the kubelet
registers with the API server, the node is Ready. There is no reason for the two
directions to take the same time, and my prediction assumed a symmetry that does
not exist in the design.

This has a production consequence. A node that reboots in under 5 minutes comes
back before the toleration expires, so **pods are never rescheduled at all**. If
the fault was in the node rather than the pod, the application stayed broken for
that whole window and Kubernetes did nothing. A node that flaps is worse than a
node that dies cleanly.

**The stuck Terminating pods** follow from the same model: the only component that
can confirm a container is actually gone is the kubelet on that node. The API
server set a deletionTimestamp, but nothing could complete the deletion while w1
was off, so the pod objects persisted. This is why
`kubectl delete pod --force --grace-period=0` exists, and why it is dangerous:
it asserts to the API server that the container is gone without knowing it. For a
Deployment that risks duplicate work; for a StatefulSet with storage it risks two
processes writing to the same volume.

## Findings not planned for

**1. The control plane accepts workloads.** The replacement pods landed on cp
(IPs in the 10.42.0.0/24 range). k3s does not taint its server node by default. An
application that exhausts memory on that node takes the API server with it, which
means losing the ability to diagnose or recover the cluster.

**2. Recovery left the cluster more fragile than the incident did.** After w1
returned, the distribution was:

- cp: 1x api, 1x web
- w2: 1x api, 1x web, postgres
- w1: Ready and completely empty

Kubernetes never rebalances. The scheduler places a pod at creation time and does
not revisit the decision. So losing cp now means losing the control plane and half
the api replicas simultaneously — a concentration of risk that nobody chose and
that no alert would report, because every pod is Running and every probe passes.

This is a latent condition: the incident is closed, the service is healthy, and
the system is in a worse state than before.

## Not measured

Whether the api Service kept listing the dead pod's endpoint (10.42.1.32) during
the 5 minutes before eviction. If it did, roughly half of all requests were being
routed to a pod that no longer existed, and the single `curl` that returned 200
had a 50% chance of hitting the surviving backend by luck. One request is not
enough to conclude the service was healthy.

The correct measurement would have been a loop recording
`kubectl get endpoints -n reflex api` alongside the HTTP status code, not the
status code alone.

## What would make this better

**1. Taint the control plane** so it stops accepting application workloads.

**2. Add `topologySpreadConstraints`** to the Deployments so replicas are forced
across nodes at scheduling time, instead of relying on whatever the scheduler
happened to pick.

**3. Postgres is the top unresolved risk.** Single replica, no persistent volume,
schedulable onto any node. The only reason this incident caused no data loss is
that the coin landed the other way. It needs a PersistentVolumeClaim at minimum.

**4. Instrument the endpoint path**, so the question above can be answered rather
than assumed. The api already exposes /metrics; the gap is that nothing scrapes it.

**5. Consider lowering `tolerationSeconds` for stateless workloads** — with the
tradeoff stated explicitly: a shorter toleration recovers faster from real node
loss but causes unnecessary churn when nodes flap. There is no free setting here,
only a choice about which failure you would rather have.
