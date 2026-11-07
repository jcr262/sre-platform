# Reflex — Lab Journal

## Sprint 1 · Oct 26 – Nov 1
**Goal:** the app runs in Docker on my laptop and data survives a restart

### 2026-10-25 — Step 1 done
- Repo `sre-platform` created, public, pushed
- Structure: reflex/api, reflex/web, .gitignore

**Errors hit**
- `Permission denied to deploy key` on push — the SSH key was registered as a
  deploy key on sre-lab instead of an account key. Moved it to Settings → SSH keys.
  Deploy key = one repo. Account key = all repos.

**Next**
- Step 2: read main.py and answer the four questions

### 2026-10-30 - Step 2 done

**Done**
- Read main.py and answered the four questions in the journal

**Answers**
- 5 environment variables: DB_HOST, DB_NAME, DB_USER, DB_PASSWORD are required; 
DB_PORT is optional (defaults to 5432). Missing a required one aborts startup 
with an explicit message naming the variable.
- The listen port is not in main.py - it is a uvicorn argument, so the Dockerfile 
decides it.
- /api/health is liveness: the process answers, nothing else. /api/ready is 
readiness: it runs a query, so it fails if the database is down. A pod can be alive 
but not ready.
- The frontend uses `cons API = '/api'` with no host, so the browser resolves it 
against the origin that served the page - nginx, not the API. Nginx has to prox 
/api/ to the api container. Same-origin.

**Corrected during review**
- Counted 6 variables, there are 5.
- Had a default backwards: thought `env("DB_PORT", "5432")` meant the variable must 
be defined. It means the opposite - if it is absent, 5432 is used.
- Containers talk to each other over internal ports, not the ports published to the 
host. Postgres listens on 5432 sinde the network even if nothing is published.

**Next**
- Step 3: write the API Dockerfile. Decide base image and the order of COPY vs 
RUN pip install.

### 2026-11-01 — Sprint 1 complete

**Done**
- API Dockerfile: python:3.11-slim, layers ordered so pip install stays cached
- Web Dockerfile: nginx:alpine, config and index.html to separate paths
- nginx.conf with /api/ proxy to the api service
- docker-compose: 3 services, named volume, healthcheck, depends_on
- .env and .env.example
- Persistence tested: restart OK, down/up OK, down -v wipes it (expected)

**Learned**
- nginx resolves proxy_pass hostnames at startup, not per request. If the
  upstream does not exist the container dies immediately.
- Service-name DNS only exists inside the Compose network. `docker run` on its
  own does not resolve other containers by name.
- COPY: source is relative to the build context, destination is inside the
  image. Two destinations means two COPY lines.
- CMD vs CMD-SHELL: without a shell, $VARIABLES are not expanded.
- Named volumes outlive containers. `down` keeps them, `down -v` destroys them.
  Same idea as a PersistentVolumeClaim in Kubernetes.
- Chose to duplicate values in .env instead of interpolating in compose, to keep
  a single file as the source of truth.

**Errors hit**
- `docker built` instead of `build` — the error named the flag, not the typo
- WORKDIR pointing at a file instead of a directory
- proxy_pass to `web` (itself) instead of `api`
- Same host port published on two services
- Circular depends_on between api and web
- Lowercase env var names; the app reads them uppercase

## Sprint 1 retro — Oct 26 to Nov 1

**Goal:** the app runs in Docker and data survives a restart
**Result:** done — all six steps

**Hours spent:** ~4, all on Nov 1
**Observed velocity:** 4 h in one day, 0 during the week

**What worked**
- Writing the files myself instead of copying templates. Every error taught
  something specific.

**What to change for Sprint 2**
- All the work landed on the last day. Use the weekday sessions.


### 2026-11-06 — Sprint 2, steps 1-3

**Done**
- Cluster up, snapshots `pre-sprint2`
- Namespace manifest applied
- Local registry running, images pushed and pulled from a node
- Secret created with secretKeyRef planned for the api Deployment

**Learned**
- The image name contains the registry address. `docker push host:5000/name:tag`
  goes there because the name says so, not because of config.
- Two separate configs for an insecure registry: /etc/docker/daemon.json on the
  laptop so Docker can push, /etc/rancher/k3s/registries.yaml on all three nodes
  so k3s can pull. Restart required on both.
- 10.182.120.1 is my laptop seen from the Multipass network, not a VM. One IP
  per network a machine is attached to.
- A manifest without metadata.namespace lands in `default`, even if the
  namespace exists. Writing it in the file beats passing -n, because the
  pipeline will not pass flags.
- Having the YAML is not the same as the object existing. apply is what creates it.

**Errors hit**
- `http: server gave HTTP response to HTTPS client` — missing insecure-registries
  in Docker's daemon.json
- Secret created in `default` because the manifest had no namespace
- .gitignore line for the real secret was never added; caught it with
  `git status -s -uall` before any add

**Time:** 3h30 — one hour of it on the registry
**Next**
- Step 4: Postgres Deployment + Service
