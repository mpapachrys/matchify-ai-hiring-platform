# Matchify.ai

A single-tenant hiring platform. One company posts roles; candidates apply and track
their progress; hiring managers review applicants and move them through a pipeline.

**Next.js 15 (App Router) · FastAPI · MongoDB · MinIO · Docker**

# Contributors

| Contributor | GitHub Profile |
| :--- | :--- |
| **Manos Papachrysanthou** | [@mpapachrys](https://github.com/mpapachrys) |
| **Dimitris Papachrysanthou** | [@DimitrisPapachrysanthou](https://github.com/DimitrisPapachrysanthou) |
| **Nikos Koukis** | [@nikos-koukis](https://github.com/nikos-koukis) |
---

## Quick start

```bash
make up
```

That builds every image, starts the stack, initialises the Mongo replica set, creates
the object-storage bucket, and seeds demo data.

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| MinIO console | http://localhost:9001 |
| MongoDB | mongodb://localhost:**27018** — 27018, not 27017, so a MongoDB installed natively on your machine can keep 27017 without the two silently colliding |

### Demo logins — password `Passw0rd!` for all

| Role | Email |
|---|---|
| Hiring Manager (admin) | `manager@matchify.dev` |
| Hiring Manager | `dimitris@matchify.dev` |
| Candidate | `nikos@example.com` |
| Candidate | `maria@example.com` |

### Common commands

```bash
make up          # build + start (dev, hot reload)
make down        # stop
make clean       # stop and delete all data volumes
make logs        # tail every service
make seed        # wipe and re-seed demo data
make test        # run the backend test suite
make types       # regenerate TS types from the OpenAPI schema
make prod        # production-shaped run (no bind mounts, no hot reload)
```

---

## Architecture

```
browser ──► :3000  web (Next.js standalone)
                │   rewrites /api/v1/* over the internal network
                ▼
            :8000  api (FastAPI) ──► mongo:27017  (replica set rs0 → transactions)
                                 └─► minio:9000   (resumes, verification documents)
```

### Why the proxy

The browser only ever talks to `localhost:3000`. Next.js rewrites `/api/v1/*` to the
API container, which makes the API's `httpOnly` cookies **first-party**. Three things
follow from that single decision:

- no CORS configuration to maintain,
- no token in `localStorage` for an XSS to steal,
- Server Components can read the session, because it lives in a cookie they can forward.

### Roles

Two roles, gated twice for two different reasons:

| Layer | Mechanism | Purpose |
|---|---|---|
| [`src/middleware.ts`](apps/web/src/middleware.ts) | reads the JS-readable `mx_role` cookie | **UX** — no flash of the wrong shell |
| [`app/candidate/layout.tsx`](apps/web/src/app/candidate/layout.tsx), [`app/manager/layout.tsx`](apps/web/src/app/manager/layout.tsx) | server-side `requireRole()` | blocks rendering |
| [`app/api/deps.py`](apps/api/app/api/deps.py) | verified JWT + database role lookup | **security** — the only one that counts |

A forged `mx_role` cookie gets you a redirect to a page whose every data call is then
rejected by FastAPI.

### Data model

Six collections plus a singleton. Full detail in [docs/data-model.md](docs/data-model.md).

```
users ──1:1──> candidate_profiles
  └──1:N──> documents, refresh_tokens

jobs ──1:N──> applications <──N:1── users (candidate)

org_settings   (exactly one document — this deployment serves one company)
```

Three decisions worth knowing:

1. **`applications` is its own collection**, not an array on `jobs` — a popular posting
   would approach the 16 MB document ceiling, and cross-job pipeline queries are
   impossible from nested arrays.
2. **Snapshots are intentional duplication.** `job_snapshot` and `resume_id` freeze at
   apply time, so editing a job or re-uploading a resume never rewrites history.
3. **`{job_id, candidate_id}` is unique.** Duplicate applications are blocked by the
   database, not by an app-layer check that races under concurrent submits. This is
   covered by a test that fires two applications concurrently.

### Where the AI team starts and we stop

Matching and scoring are a separate team's, built on a Neo4j graph outside this
codebase. The whole interface between us is a read-only export —
[docs/graph-export.md](docs/graph-export.md) is that handoff. No score is
computed or stored here.

The one place this platform calls an LLM is **resume parsing**: a candidate
uploads a CV, a model extracts structure from it in the background, and the
candidate reviews the result before it touches their profile. It sits behind a
`Protocol` in
[`app/integrations/resume_parser/protocol.py`](apps/api/app/integrations/resume_parser/protocol.py):

```bash
RESUME_PARSER=stub         # regex-only placeholder — the default, so the platform runs with no API key
RESUME_PARSER=openrouter   # a real model via OPENROUTER_API_KEY / AI_MODEL
```

Nothing outside that package imports an implementation directly, and an
unconfigured key falls back to the stub rather than failing the upload.

---

## Layout

```
apps/
  web/                      Next.js 15 · App Router · TypeScript · Tailwind v4
    src/middleware.ts       role guard (UX layer) + silent token refresh
    src/app/
      (auth)/               login, register — centred card, no shell
      candidate/            role-gated subtree: dashboard, jobs, applications, profile, documents
      manager/              role-gated subtree: dashboard, jobs, applicants, pipeline, organization
    src/components/         ui primitives, charts, layout shell, feature components
    src/lib/api/            server.ts (RSC fetch) · client.ts (browser fetch + refresh)

  api/                      FastAPI · Python 3.12 · Beanie ODM
    app/core/               config, argon2 + JWT, domain exceptions
    app/models/             Beanie documents — schema and indexes live together
    app/schemas/            Pydantic DTOs — documents are never returned raw
    app/api/deps.py         🔒 authentication and role gates
    app/api/v1/routes/      thin HTTP layer
    app/services/           business logic, no FastAPI imports
    app/integrations/resume_parser/   🔌 the only LLM call in the platform
    tests/                  pytest — auth, RBAC, and the full hiring flow

infra/minio/init.sh         creates the private bucket
packages/api-types/         generated TypeScript types (make types)
docs/
```

---

## Testing

```bash
make test
```

Tests run against a real MongoDB in a throwaway database — the unique index and the
transaction are load-bearing behaviour, and mocking them out would test nothing.

Covered: cookie flags and token rotation, refresh-token replay detection, every role
boundary, the full apply → stage-change flow, and two concurrent applications racing
for the same job.

---

## Deployment

The GitLab runner lives **on the deployment server** with the shell executor, so
the pipeline needs no container registry, no deploy SSH key and no
docker-in-docker: the box builds images for itself and starts them from its own
daemon.

That shape was chosen because the academy's GitLab provides no shared runners,
and self-hosting one on the target machine solves three problems at once — a
runner exists, it is `x86_64` (a dev Mac produces `arm64` images that will not
start on the server), and the images never have to travel.

The cost is that `next build` — which peaks at 2–4 GB — runs on the same box as
the database. The build job is therefore deliberately **sequential**, and the
server has 4 GB of swap as a floor under the spike.

### Hostnames

| Host | Serves |
|---|---|
| `matchify.gr` | Next.js — which proxies `/api/v1/*` internally, so cookies stay first-party |
| `www.matchify.gr` | 301 to the apex, so the session cookie has one origin |
| `api.matchify.gr` | FastAPI directly — `/docs`, `/openapi.json`, and the graph export |
| `files.matchify.gr` | MinIO. Presigned URLs are signed for this host, so a proxy cannot rewrite it |

```bash
# on the server, once
mkdir -p /srv/matchify && cd /srv/matchify
# copy docker-compose.yml, docker-compose.prod.yml and .env here — nothing else

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Interview scheduling (calendar-mcp)

`calendar-mcp` reads its config from the same root `.env` as everything
else (Google OAuth client credentials, its own OpenRouter key, the shared
`CALENDAR_ASSISTANT_TOKEN`) — `docker-compose.yml` passes those through to
its container environment, so there's no second `.env` file to place on
the server.

The one file it still needs out-of-band is the OAuth token cache:

```bash
mkdir -p /srv/matchify/mcp_calendar
# copy mcp_calendar/.gcp-saved-tokens.json here
```

That file comes from a one-time, interactive Google OAuth consent completed
locally (see `mcp_calendar/README.md`) — the container has no browser and
never runs that flow itself, only refreshes the saved token. If the refresh
token is ever revoked, interview scheduling starts failing until someone
redoes that local flow and re-copies the token file.

**Always pass both `-f` files.** Naming them explicitly is also what stops
Docker auto-loading `docker-compose.override.yml`, which would silently
re-enable dev bind mounts and hot reload in production.

The prod overlay replaces `build:` with `image:`, caps memory per service, and
takes MongoDB and MinIO off the public interface — the API and web bind to
`127.0.0.1` only, so a reverse proxy terminates TLS in front of them.

### Demo data on a live deployment

Two manual buttons in the pipeline — `seed:demo-data` and `clear:demo-data` —
rather than an SSH session, so filling or emptying the live database is a
deliberate, attributable act.

Seeding a production deployment requires a `SEED_PASSWORD` CI/CD variable. The
seeder refuses to run without it, because the demo hiring manager is an admin
and its default password is published in this README.

Manager self-signup is off in production, so there is no UI path to the first
manager after a wipe. The `create:manager` button (or `app/db/create_manager.py`
directly) makes one; its password comes from a `MANAGER_PASSWORD` CI/CD variable
and is never taken as a flag.

### Inspecting the production database

MongoDB is not published on the host — it listens only on the internal Docker
network — so reaching it means tunnelling in over SSH. Its container IP can
change across restarts, so the tunnel resolves it fresh each time:

```bash
MONGO_IP=$(ssh -i ~/.ssh/id_ed25519_matchify deploy@169.58.68.46 \
  "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' matchify-mongo")
ssh -i ~/.ssh/id_ed25519_matchify -N -L 27020:$MONGO_IP:27017 deploy@169.58.68.46
```

That prints nothing and stays running — leave it open. Point Compass (or
`mongosh`) at:

```
mongodb://localhost:27020/matchify?directConnection=true
```

`directConnection=true` is required: without it the client tries to reach the
replica-set members by their internal names (`mongo:27017`), which do not
resolve on your machine. Close the tunnel with Ctrl-C when done.

### Sizing

A single node runs the whole stack comfortably in **12 GB**. The one setting
that must not be left to defaults is memory: WiredTiger otherwise takes ~50% of
host RAM and then fights the JVM heap of Neo4j for the remainder.

| | RAM |
|---|---|
| Neo4j heap + page cache | 4 GB |
| MongoDB cache (`MONGO_CACHE_GB`) | 1.5 GB |
| api + web + MinIO | ~0.8 GB |
| OS + Docker | ~1 GB |
| headroom | ~4 GB |

---

## Production hardening

This scaffold is set up for local development. Before deploying:

- [ ] `JWT_SECRET` — generate with `openssl rand -hex 32`
- [ ] `COOKIE_SECURE=true` and serve over HTTPS
- [ ] `ALLOW_MANAGER_SIGNUP=false` — otherwise anyone can self-register as a manager
- [ ] `SEED_ON_STARTUP=false`
- [ ] MongoDB authentication + a keyfile for the replica set; drop the host port mapping
- [ ] Real `STORAGE_ACCESS_KEY` / `STORAGE_SECRET_KEY` instead of the dev defaults, and
      point `STORAGE_ENDPOINT_PUBLIC` at your MinIO host over HTTPS
- [ ] Rate limiting on `/auth/login` and `/auth/register`
