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



