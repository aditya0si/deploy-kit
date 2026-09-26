# Productization Audit — Aditya Singh engineering portfolio

**Auditor:** Hermes deployment/productization subagent (deepseek-v4.1-flash)
**Date:** 2026-09-27
**Mode:** read-only except for this report. No project repo, Git state, provider, or GitHub object was modified.
**Primary deployment system:** `C:/Users/oliad/Desktop/deploy-kit`
**Evidence classes used below:** `LOCAL` = file/command on this machine; `REMOTE` = GitHub/probe over the network; `RECOMMENDATION` = proposed, not yet true.

---

## 1. Executive verdict — what "project to product" must mean here

For this portfolio, **"product" is not "has a README and a CI badge."** The repos already over-index on long,
honest engineering writeups (many are excellent). What is missing is the *last mile*: a stranger can open a URL,
see the thing work, and know which revision is running. The deploy-kit already encodes the correct doctrine
("a 200 is not live", "the deployed revision is the pushed revision"). The audit below is largely about applying
that doctrine to the actual portfolio and fixing the two things that make it under-deliver:

1. **The deploy-kit is strong but unadopted.** No local repository calls its reusable workflows (verified). Its
   manifest tracks 13 live surfaces, all of which I probed HTTP 200 with the declared body marker — but the
   manifest omits at least one live app (`samjho`) and includes flagship fronts whose backends are not deployed
   (schemeGPT, samjho). So the manifest proves *pages serve*, not *products work*.
2. **The strongest engineering repos have no user-facing surface at all.** `tenant-api-platform`,
   `event-stream-platform`, `grounded-knowledge-platform`, `stockflow`, `aegis`, `Sentinel`, `pharmforge`,
   `marketplace`, `vibe-odds` are all `Live / Deployment URL: None` (verified locally and against GitHub
   metadata). They are excellent *engineering evidence*, poor *product evidence*, and a recruiter cannot click them.

Therefore "project to product" for this portfolio means, concretely, seven things per shipped project:

- **Product surface** — one URL a non-technical reviewer can open and operate in <60 s, with an obvious first action.
- **Reliable deployment** — reproducible, free-tier, revision-pinned; a push redeploys and the running revision is identifiable.
- **CI** — a workflow that can actually fail, on the default branch, whose result is visible (badge/run link), and which runs the same commands documented locally.
- **Observability** — at minimum a `/health` (and ideally `/readyz` + `/metrics`) that the deploy step itself probes, plus a status page.
- **Demo path** — seeded/demo data so the product is non-empty on first load, with a scripted click-path.
- **Documentation** — README top-third = what it is, live URL, stack, how to run, and an explicit "what is not built".
- **Honest evidence** — every numeric claim traceable to a committed artifact or reproducible command; conceptual vs production-grade labelled.

The portfolio already contains a serious evidence-ledger approach (`Portfolio/research/`, `repo-intel/REPO_GRADES.md`).
This report does not replace those; it converts them into shipping decisions.

---

## 2. Audited inventory (locally verifiable candidates)

**Method.** Every path below exists on this machine and was inspected. "CI (latest run)" is `REMOTE` from
`gh run list --repo <repo> --limit 3` on the default branch. "Live probe" is an HTTP probe performed today.
Where I did not inspect a file, the cell says `unknown`. Dependency/build dirs (`node_modules`, `.venv`, `dist`,
`.git`) were not audited.

### 2.1 Summary table

| Project | Path | Stack | CI (latest run, REMOTE) | Live probe today | Deploy signal on disk | Disposition |
|---|---|---|---|---|---|---|
| CoverAI | `insurance/` (canonical) | Next.js + FastAPI + pgvector, pnpm/turbo | success (main) | `cover-ai-web…vercel.app` 200 + marker (LOCAL/REMOTE) | Vercel front (no `vercel.json`), Dockerfile, compose | **ship now** (verify API) |
| schemeGPT | `SchemeGPT/` | FastAPI + Next.js 15/16 + pgvector + Groq | main CI success; local branch `field-ops…` quality gate **failed** | web 200 + marker; `schemegpt-api.fly.dev` **DNS fail** | `fly.toml`, `Dockerfile`, `docs/DEPLOY.md` | **repair then ship** |
| tenant-api-platform | `tenant-api-platform/` | Go, Postgres RLS, Redis, outbox | success (main) | none | Dockerfile, compose, Makefile, load artifacts | **repair then ship** (add live API + seeded demo) |
| event-stream-platform | `event-stream-platform/` | Go, Redpanda, Postgres, SSE viewer | success (main) | none | Dockerfile, compose, Makefile, load artifacts | **repair then ship** |
| grounded-knowledge-platform | `grounded-knowledge-platform/` | Python, FastAPI, pgvector, uv | ci success + eval success | none | compose, Makefile, eval CI | **repair then ship** |
| samjho | `samjho/` | Python, FastAPI, pgvector, Next.js | ci success, eval **failure** (master) | web 200 (`samjho-adityasinghprojects.vercel.app`), **not in sites.json** | `infra/docker-compose.yml`, 2 Dockerfiles, CI | **repair then ship** |
| vibe-odds | `vibe-odds/` | Python, FastAPI + HTML, ML | **no workflows** (no runs) | none | requirements only; no Dockerfile/vercel | **repair then ship** |
| E-commerce-Dashboard (Olist BI) | `ecom-dashboard-work/` | Streamlit + SQL/SQLite | **no runs** | none | `.streamlit/`, README Streamlit-Cloud path | **ship now** (fastest dashboard) |
| Portfolio | `Portfolio/` | Next.js 16 + Express, Playwright/axe | quality gates success (main) | 200 + marker; revision URL 200 | `vercel.json`, `.vercel`, full evidence docs | **ship now** (already live) |
| pharmforge | `pharmforge/` | Python, RDKit, agentic RAG | success (master) | none | Dockerfile, compose | **keep as engineering evidence** (or wave-2 ship) |
| aegis | `aegis/` | Python, MCP proxy, OTel | success (master) | none | Dockerfile, compose | **keep as engineering evidence** |
| Sentinel | `Sentinal/` (repo `Sentinel`) | Python, FastAPI guardrails | quality-gate success (main) | none | compose | **keep as engineering evidence** |
| stockflow | `stockflow/` | Go + React operator UI | **no remote** (no runs) | none | Dockerfile, compose, Makefile, release-evidence | **repair then ship** (publish first) |
| DevAtlas | `geomap/` (repo `DevAtlas`) | FastAPI + PostGIS + Next.js | sync workflow **failing** (2026-09-26); CI unknown | none | `vercel.json`, `railway.json`, firebase, k8s | **repair then ship** |
| agent-report-distribution | `portfolio-3pack/01-…/` | Python, AWS serverless, Terraform, moto | success (latest), earlier failure | none | Terraform + docs; free-tier chunker path | **repair then ship** (defects open) |
| cadenza | `portfolio-3pack/02-…/` | MERN/TS, Socket.IO, Clerk | success (main) | none (guessed `cadenza.vercel.app` → HTTP 500, ignore) | compose dev; DEPLOY.md | **repair then ship** (auth fail-open open) |
| real-time-bidding | `portfolio-3pack/03-…/` | React + Node + Socket.IO + Mongo | success (main) | none | compose dev; loadtest workflow | **repair then ship** |
| marketplace | `marketplace/` | Python (agent-evolution bench) | **no remote** | none | pyproject only | **keep as engineering evidence** (unpublished) |
| mcp-from-scratch | `mcp-from-scratch/` | Python stdlib JSON-RPC/MCP | **no workflows** | none | pyproject | **keep as engineering evidence** |
| architecture.bitnet | `architecture.bitnet/` | Python/PyTorch fine-tune | no remote | none | pyproject, docs | **keep as engineering evidence** |
| PulseGrid | `PulseGrid/` | Python, Kafka/ClickHouse (spec) | **no remote** | none | pyproject only | **keep** (spec-stage; repo-intel says 206 tests local green) |
| llm-robustness-eval | `llm-robustness-eval/` | Python research | no remote | none | requirements, results | **keep** |
| TheButterFlyEffect | `TheButterFlyEffect/` | Streamlit, Neo4j/NetworkX | no runs | none | none (no CI) | **keep/deprioritize** |
| CyberSec (`Cyber`) | `CyberSec/` | FastAPI + Next.js + LangGraph | success (main) | none | compose, uv | **keep as engineering evidence** |
| visionpro (`HandyMan`) | `visionpro/` | TS/React spatial UI | success (main) | none | Dockerfile, compose, CI | **archive/deprioritize** |
| Agentic Research (`agentic_rag_system`) | `Agentic Research/` | FastAPI + Next + Chroma | success (main) | none | compose, Dockerfiles | **archive/deprioritize** |
| OpenCode-Team | `opencodeteam/` | TS CLI, npm `opencode-teamwork` | not probed | npm package (README) | none | **keep** (only published artifact) |
| cisco hardware labs | `cisco projs/` (+ 6 GitHub Pages repos) | static HTML + RTL/sim | not probed | 6× `aditya0si.github.io/*` 200 + markers | Pages, umbrella CI | **ship now** (already live) |
| CosmosSteller | `src/` (repo `CosmosSteller`) | React/TS | no runs | 200 + marker | Vercel web | **archive/deprioritize** (repo-intel: early coursework) |
| fiver (LeadForge) | `fiver/` | TS monorepo, LLM client | no remote | none | node_modules committed present | **archive/deprioritize** |
| ecom/ott extra analytics | `ott-content-analytics/` | Streamlit, synthetic data | no remote | none | requirements | **keep** (media-role only; 100% synthetic) |
| SIH rejects / Projectss / education / Sem-* | various | mixed | n/a | n/a | n/a | **archive/deprioritize** |

> Prior audits found the same shape from the other direction: `Portfolio/docs/portfolio/INITIAL-AUDIT.md` (dated
> 2026-09-19) scored 15 projects and listed 12 excluded repos; `repo-intel/REPO_GRADES.md` (2026-09-09) carries
> a per-resume slate. Neither supersedes the live probes above, and both are now partly stale (e.g. repo-intel
> marks `vibe-odds` "UNPUBLISHED (no .git)", but it now has a GitHub remote — verified).

### 2.2 Notable per-project detail

**CoverAI** — `insurance/` remote = `aditya0si/CoverAI`, branch `main`, last commit `8855024` (docs pitch deck).
Live front `cover-ai-web-adityasinghprojects.vercel.app` returns 200 with marker "CoverAI — Intelligent Vehicle
Insurance Copilot" (52,568 B). Stack is a pnpm/turbo monorepo (`apps/web` Next 14, `apps/api` FastAPI, pgvector
service in CI). CI run success on `main`. **Unknown:** whether the live front reaches a live API (I only verified
the HTML marker). A duplicate clone exists at `gh-cleanup/CoverAI` (older HEAD `af0e8e5`) — a duplicate-project
risk, not the canonical tree. Strongest value: end-to-end insurance claim lifecycle (customer → triage → adjudicate)
is a legible FDE/SWE story. Gap: no `vercel.json`; API deploy path only implied in README.

**schemeGPT** — remote default `main`; **local checkout is on `field-ops-and-deployment-kit`**, and the latest
GitHub run for that branch is the *quality gate* → **failure** ("Deterministic RAG quality ga…"). The deployed web
is live with the documented marker, but the documented API host `schemegpt-api.fly.dev` **does not resolve**
(`getaddrinfo failed`), and `docs/DEPLOY.md` prescribes Fly.io — which deploy-kit correctly classifies as *not
free*. Net: the front serves, but live Q&A is either running via the API proxy env var pointing elsewhere or in
zero-key retrieval-only fallback. 2,226 tracked files (largest repo here). Treat the failing branch as a gate to
close before re-deploying.

**samjho** — remote `aditya0si/samjho`, default `master`. Live web 200 (19,904 B, Next.js) at
`samjho-adityasinghprojects.vercel.app`; **not present in `deploy-kit/sites.json`** (manifest drift). README states
plainly that the API is *not* deployed (needs ~2 GB RAM + pgvector Postgres) and the site shows an honest degraded
state; the README also claims CI "never executed on GitHub", but `gh run list` shows `ci` **success** and `eval`
**failure** on 2026-09-20 — a stale doc claim to correct. Excellent honesty; the product is a two-tier app with only
the top tier live.

**tenant-api-platform / event-stream-platform / grounded-knowledge-platform / stockflow** — the strongest *systems*
evidence and all currently **invisible as products**. Each has a green CI run on the default branch, real service
dependencies in CI (Postgres/Redis/Redpanda), committed load/benchmark artifacts, and a Makefile of reproducible
commands — but no deployed URL, no homepage in GitHub metadata. `stockflow` has **no Git remote at all** (local-only;
its own README says the Linux CI workflow "has not yet been observed on a remote CI run"). These four are the best
candidates for a genuine free-tier demo *if* a read-only hosted surface (seeded API + `/docs` or a read-only viewer)
is built; the full stacks (Redpanda etc.) do not fit free tiers as-is.

**DevAtlas** — `geomap/` is the canonical tree (remote `aditya0si/DevAtlas`); `gh-cleanup/DevAtlas` is an older
duplicate. A scheduled *Sync Indian GitHub Developer* workflow has failed on each of its last three runs
(2026-09-26). Has `vercel.json` + `railway.json` + Firebase config + k8s manifests, but no configured path is
currently serving. Response: fix the sync failure or disable the schedule; do not claim a live demo.

**portfolio-3pack** (agent-report-distribution, cadenza, real-time-bidding) — three freshly built, well-reviewed
repos, each with green CI on the latest `main` (cadenza and bidding verified success). They are **not deployed** and
carry open correctness/security defects tracked in `portfolio-3pack/MEMORY.md` (e.g. cadenza production auth
fail-open when `AUTH_MODE=demo`; bidding orphan-row race; agent-report presign authz bypass + a commission
quantisation money bug). Ship-blockers are real and known.

**Portfolio** — the site itself is the only fully operational *product* today: live, marker-verified, evidence
validators in CI, `deployment-verification.md` with revision SHA + headers, Playwright/axe + Gitleaks. It is the
model to copy.

**Two prior-audit conflicts to resolve** (mark as unverified until checked): `INITIAL-AUDIT.md` calls
`agentic_rag_system` a private workspace, but `gh repo view` reports it **PUBLIC**; and `repo-intel` calls
`vibe-odds` unpublished, but it now has an `aditya0si/vibe-odds` remote.

---

## 3. Ranked top-10 shipping portfolio

Optimised for recruiter clarity, differentiated evidence, usable demos, operational credibility, and role coverage —
**not** repo count or test count.

| # | Project | Why it ranks | Primary role signal | Live now? |
|---|---|---|---|---|
| 1 | **CoverAI** | Full claim lifecycle, live web, real domain, CI green | FDE / Software Engineer | Yes (web); API unverified |
| 2 | **schemeGPT** | Best-known RAG product; hybrid retrieval + quote verification; live web | AI Engineer | Web yes; API no |
| 3 | **tenant-api-platform** | Deepest backend/security evidence (RLS enforced twice, 304 tests, 14 ADRs) | Backend / Platform | No |
| 4 | **event-stream-platform** | Orthogonal streaming evidence; measured NFRs; browser viewer exists | Backend / Data / Systems | No |
| 5 | **grounded-knowledge-platform** | "Harness that can fail" RAG; measurable retrieval + ACL | ML Systems / AI Platform | No |
| 6 | **samjho** | Honest two-tier AI product; live web with graceful degradation | FDE / AI Product | Web yes; API no |
| 7 | **Portfolio** | The catalog itself; already revision-verified | Whole-profile | Yes |
| 8 | **vibe-odds** | Differentiated DS/analytics + pre-registration rigor | Data / ML | No (needs publish+host) |
| 9 | **real-time-bidding-platform** | Concurrency correctness + load test; realtime full-stack | Full-Stack / SWE | No |
| 10 | **agent-report-distribution** | FDE data-pipeline story; free-tier Lambda path | FDE / Data Engineer | No |

**Alternates / role fillers:** `pharmforge` and `aegis` (AI-safety + agentic-science) if the portfolio needs a
security/agentic slot more than a third backend; `E-commerce-Dashboard` (Streamlit) as the fastest *live* dashboard
to add while backend demos are being built; the six `aditya0si.github.io` hardware labs as a differentiated
hardware/embedded cluster (already live, keep as a labelled side-lane, not as SWE/AI flagships).

Deliberately **excluded from the top 10:** `CosmosSteller`, `visionpro/HandyMan`, `fiver/LeadForge`,
`TheButterFlyEffect`, `Agentic Research`, the rejected SIH repos — either archived coursework, superseded, or
without CI/build on disk.

---

## 4. Three-wave execution roadmap

Format per project: **gate commands** (discovered on disk), **live markers** (proposed), **CI expectation**,
**deploy target**, **done**. "Free backbone" per deploy-kit: Vercel (frontends) · Netlify (static+functions) ·
Cloudflare (edge APIs) · GitHub Pages (static/docs) · Render (containers tolerating cold start; use Neon/Supabase
for durable DB) · Streamlit (dashboards).

### Wave 1 — fastest credible live wins (surfaces a reviewer can click this week)

**1. deploy-kit status page + manifest hygiene**
- Gate: `python bin/deployctl.py selftest` (verified today: `selftest: OK`, 10 workflows, 5 stacks, 7 targets) and `python bin/deployctl.py status`.
- Fix: add `samjho` to `sites.json`; add a `marker` for `deploy-kit-proof` already present; add `schemeGPT` **API** health as a separate entry only once it resolves.
- Live marker: `aditya0si-live.netlify.app` already contains "Live surfaces".
- Done: `status` reports every manifest row with a fresh CI conclusion and a liveness verdict; no row is `-`.

**2. CoverAI — confirm the live product, don't just trust the HTML**
- Gate (local): `pnpm install && make test` or per `insurance/README.md` (Poetry API + Playwright e2e); CI already runs `ci.yml`.
- Live markers: keep web marker; add an API health URL marker (e.g. `"status":"ok"`) once the API is deployed.
- Deploy target: Vercel (web) + Render or Cloudflare (API); Postgres on Neon/Supabase (pgvector).
- Done: from the live URL a reviewer uploads a demo image, sees triage output, and the profile shows adjudication; the deploy step probes the API `/health`.

**3. E-commerce-Dashboard (Olist BI) — the fastest free live dashboard**
- Gate: `pip install -r requirements.txt && python -m scripts.pipeline && python -m pytest tests/ -q` (README states 8 passed) → `streamlit run dashboard/app.py`.
- Live marker: a stable KPI string, e.g. `R$ 13.22M` or "Overview".
- Deploy target: Streamlit Community Cloud (main file `dashboard/app.py`); no secrets.
- Done: public Streamlit URL renders all 6 pages with data built from committed `data/raw/`.

**4. Portfolio — already live; wire it to the roadmap**
- Gate: `npm test && npm run lint && npx tsc --project portfolio/tsconfig.json --noEmit && npm run build && npm run test:e2e`.
- Done: every project card links to a live URL **or** is explicitly labelled "engineering case study — no live demo".

### Wave 2 — backend/data/agent products that need operational work

**5. tenant-api-platform**
- Gate (local, Docker): `make up` then `make test`; CI reference: `gofmt`, `go vet`, migrations, full `-race` suite, `docker compose config`, a third job that starts the deployed stack and smoke-tests it.
- Live: deploy **only** a read-only demo surface — API on Render (cold start ~30 s stated in README) + Neon Postgres + Upstash Redis; expose a seeded tenant + `/metrics` + OpenAPI. Marker: `"status":"ok"` on `/health` and a `/docs` title.
- Done: anonymous reviewer can hit `/health`, `/metrics`, and a read-only seeded endpoint; README states cold start and that writes need a tenant.

**6. event-stream-platform**
- Gate: `make up` → `make smoke` → `make demo` (viewer `http://localhost:8082/`) → `make test`.
- Free-tier reality: full stack (Redpanda) will not run free. Options (RECOMMENDATION): deploy only the SSE viewer as a static reconstruct-from-artifact demo (Pages/Vercel), or a single-process demo container on Render with recorded events. Marker: "live map" / viewer title.
- Done: a hosted URL shows the pipeline concept with recorded data, clearly labelled "recorded run, not a live broker".

**7. grounded-knowledge-platform**
- Gate: `make check` (delegates to `python scripts/tasks.py check`); eval via `eval.yml`.
- Live: read-only query API on Render + Neon pgvector, seeded corpus + gold questions; marker on `/health` and a query UI string.
- Done: reviewer submits a query, gets a grounded answer with cited chunks; `/metrics` shows retrieval counts.

**8. samjho**
- Gate (per README): `uv run pytest -m unit` (148 passed), `uv run ruff check .`, `uv run mypy .`, `python -m evals.run_eval --subjects all` (GATE PASSED), `docker compose -f infra/docker-compose.yml config`.
- Fix doc: README's "CI never executed on GitHub" is false (ci success, eval failure on 2026-09-20) — correct it; add to `sites.json`.
- Live: API on Render (~2 GB) + Neon pgvector + bring-your-own-corpus demo; web already live. Marker: existing web text plus API `/health`.
- Done: live web reaches the live API; asking an in-syllabus question returns a cited answer from the demo corpus, and off-syllabus refuses honestly.

**9. vibe-odds**
- Gate: `python -m pytest -q` (README: 251 tests; the modelling slice 49 + evidence guards) → `python -m uvicorn backend.api.server:app --port 8000`.
- Missing: no CI workflow, no Dockerfile, no deploy config. Add `ci.yml` (via `deployctl ci`) and a deploy path.
- Live: FastAPI + static site on Render free (mock mode when no `ODDS_API_KEY`); marker "feed: mock" or site title. Do **not** enable real odds keys in a public demo without rate-limit thinking.
- Done: public URL serves the evidence site in mock mode; tests green in CI.

**10. agent-report-distribution / real-time-bidding-platform / cadenza**
- Gates: 01: `ruff`, `mypy`, `pytest --cov`, `terraform fmt/validate` (per MEMORY.md). 03: `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `npm run e2e`, concurrency proof, `node server/scripts/loadtest.mjs`. 02: `lint+typecheck+test+build+e2e`.
- Blocker: close the open defects in `portfolio-3pack/MEMORY.md` (cadenza production auth fail-open, secret-scan red, bidding orphan-row race, agent-report presign authz + money quantisation) **before** any deploy.
- Live: cadenza → Vercel (client) + Render (server) + Atlas Mongo; bidding → Vercel + Render + Atlas; agent-report → keep as IaC/moto evidence, optional free-tier Lambda demo.
- Done: per-repo, security fixes committed, 3 consecutive green full-suite runs, then a hosted URL with a seed script.

### Wave 3 — deeper flagship / infrastructure products

**11. DevAtlas** — fix/disable the failing `Sync Indian GitHub Developer` schedule; then decide Vercel (front) + Render (API) + Neon/PostGIS; gate `uv run ruff check . && uv run pytest` (backend) and the frontend job in `geomap/.github/workflows/ci.yml`.
**12. stockflow** — first `git init`+create remote (none exists), push, observe CI; then host as a single-binary demo on Render + Postgres; gate `make verify` (`test web-format-check web-typecheck web-test demo`). Note its README's own honesty: CI "not yet observed on a remote run".
**13. PulseGrid** — spec-heavy; repo-intel claims 206 tests green locally but the repo is unpublished. Decide whether to build the demo (Kafka/ClickHouse will not fit free tiers) or keep as architecture evidence.
**14. marketplace (agent-evolution)** / **llm-robustness-eval** / **architecture.bitnet** — publish if the story needs an MLOps/eval or a fine-tuning flagship; otherwise keep as evidence.
**15. pharmforge / aegis / Sentinel / CyberSec** — retain as differentiated AI-safety/agentic evidence; optionally host a read-only FastAPI `/docs` + demo on Render (pharmforge has a single-command local run and a Dockerfile).

**Cross-cutting CI expectation for every shipped repo:** a workflow that can fail, running on the default branch,
using the same commands as local, with no `continue-on-error` on test steps. The best existing examples are
`tenant-api-platform`, `event-stream-platform`, `grounded-knowledge-platform`, `samjho`, `Portfolio`, `CyberSec`.

---

## 5. Deployment architecture critique — deploy-kit

### 5.1 What is genuinely strong (LOCAL, verified)

- **Two-layer separation** (reusable CI here; platform-native CD) is sound and documented (`README.md`).
- **"A 200 is not live"** is enforced: `deploy-vercel.yml` / `deploy-netlify.yml` fetch the body and `grep -qF` the marker, failing the job (`deploy-vercel.yml:47-55`).
- **Revision-to-live** is addressed: `watch_ci()` waits for a run whose `headSha` matches local `HEAD`, and treats "no run observed" as failure (`bin/deployctl.py:458-496`).
- **Selftest** is real and passing: `python bin/deployctl.py selftest` → `selftest: OK` (10 workflows, 5 stacks, 7 targets) today.
- **No secrets in logs**: `cmd_secrets` uses `gh secret set --body` and prints key names + lengths only.
- **Free-tier honesty** is unusually good and should be kept.

### 5.2 Where it can create false-green status

1. **`ci-static.yml` is broken for callers.** It runs `python3 scripts/check_links.py` in the **caller's**
   working directory (`ci-static.yml:28-30`), but `scripts/check_links.py` exists only in deploy-kit
   (verified: it is the only copy on disk) and no step fetches it. Any repo that adopts `ci-static.yml` without
   vendoring the script fails — or, worse, if someone adds it with `|| true`, silently passes. Either vendor the
   script into generated repos, or run it from a `uses:` checkout of deploy-kit.
2. **"Green" can mean "nothing ran."** `ci-node.yml` logs `::notice::` and passes when there is no `test`/`lint`/
   `build` script; `ci-python.yml` passes with a notice when no pytest suite is detected. The README frames this as
   intentional ("everything that exists passed"), but a recruiter reading a green badge cannot tell the difference
   between "tested" and "nothing to test." Recommend an explicit job summary line (e.g. counts) and a required-input
   escape hatch for projects that must have tests.
3. **`cmd_status()` picks the single most recent run on the default branch** (`deployctl.py:538-544`) without
   filtering by workflow. A green Dependabot/`sync-*` run can be reported as "CI green" while the real CI job is red.
   (`DevAtlas` currently shows a failing *sync* workflow as the latest run — the inverse problem, but the same
   root cause: workflow identity is not pinned.)
4. **`verify` markers can validate a stale or partial product.** `schemeGPT`'s web marker passes while its API host
   does not resolve; `CoverAI`'s marker passes without proving the API is reachable. Marker-passing must be paired
   with an API/health marker for two-tier products.
5. **Render has no deploy workflow.** `TARGETS["render"] = (None, [], True)` and `deploy_caller()` returns `None`
   for it, so a Render-target project gets CI but **no** automated deploy or post-deploy verification — the exact
   guarantee the kit exists to provide. There is no `render.yaml` anywhere on disk.
6. **No `environment:`/approval or concurrency guard on `deploy-vercel.yml` / `deploy-netlify.yml`**, so overlapping
   pushes can race; and both use `npx --yes …@latest`, which is non-reproducible and a supply-chain surface.
7. **`deploy-pages.yml` default `artifact-path: "."`** would upload the entire checkout; and `deploy-cloudflare.yml`
   has no marker/health verification at all.
8. **`docker-ghcr.yml` pushes an image but does not deploy**, yet `STACKS["docker"]` maps to it as if it were the
   deploy answer. Clarify that GHCR is a registry step, not a deployment.

### 5.3 Missing provider/auth paths

- No **Cloudflare Workers → Pages** distinction (Workers via `wrangler deploy` vs Pages via `wrangler pages deploy`).
- No **Streamlit Community Cloud** path in `TARGETS` (README discusses it but `deployctl` cannot scaffold/verify it).
- No **Neon/Supabase** free-Postgres provision or connection-check helper, despite the README telling users to put
  durable data there.
- No **custom domain / DNS** handling (correctly out of scope for read-only, but a product needs it eventually).
- Auth: `secrets` assumes `gh` repo scope (present: `gist, read:org, repo, workflow`, verified). No check for
  `NETLIFY_*`/`VERCEL_*` token presence before scaffolding a deploy caller, so a scaffolded deploy silently lacks secrets.

### 5.4 Revision-to-live, rollback, monitoring

- Revision-to-live is enforced only for the **first** deploy (the caller waits on the matching `headSha` run).
  Ongoing platform git-integration deploys (the README's preferred CD path) have **no** revision-lock or
  verification back in the repo — a Vercel auto-deploy can serve a revision the manifest never checked.
- **No rollback**: nothing records "last known good" URL/SHA or offers `deployctl rollback`.
- **Monitoring** is a manual snapshot (`cmd_site`, explicitly labelled a snapshot, `deployctl.py:589-614`), not a
  scheduled probe. A scheduled CI job that runs `deployctl status --json` and fails on any DOWN would turn the
  snapshot into monitoring.

### 5.5 Minimum changes before broad rollout (RECOMMENDATION)

1. Fix/vendor `check_links.py` so `ci-static.yml` works for callers (or `uses:` a deploy-kit checkout).
2. Make `cmd_status` filter by the CI workflow(s), not any workflow.
3. Add per-project **API/health markers** to `sites.json` and a second probe for two-tier apps.
4. Add a real `render.yaml` + a `deploy-render.yml` reusable workflow (deploy + marker verify), or drop Render from
   the "supported" list.
5. Add `concurrency:` + pinned action versions (replace `@latest`) to all deploy workflows.
6. Add a scheduled `status` workflow (monitoring) and a `deployctl rollback`-style record of last-known-good.
7. Adopt the kit in at least the top 3 projects so its guarantees are exercised on real repos.

---

## 6. Portfolio integration plan

**Repo metadata.** For every shipped repo set GitHub `homepageUrl` to the live URL and a one-line description that
matches the README's first sentence. Currently only `CoverAI`, `schemeGPT`, `portfolio`, `CosmosSteller` declare a
homepage (verified via `gh repo view`); `tenant-api`, `event-stream`, `grounded`, `samjho`, `vibe-odds` declare
nothing.

**Screenshots / demo scripts.** Each shipped repo gets (a) a 1–2 image hero from `Portfolio/shots/`-style capture,
and (b) a `DEMO.md` with a numbered click-path and expected outputs. `SchemeGPT`, `samjho` and `CyberSec` already
have demo/rehearsal artifacts to reuse.

**Architecture diagrams.** Several repos already have strong Mermaid/text diagrams (`tenant-api-platform`,
`event-stream-platform`, `cadenza`, `real-time-bidding`, `pharmforge`). Standardise on one Mermaid block in the
README top-third + a rendered SVG in `docs/`.

**Status/health evidence.** Promote `deploy-kit/site/index.html` (the live-surfaces status page) and link it from the
portfolio. A green CI run is a test verdict; "live" means 200 + marker — state both, as the page already does.

**Ordering on the portfolio.** Group by role, not by count:
- *AI Engineer:* schemeGPT, grounded-knowledge-platform, samjho, pharmforge.
- *Forward Deployed / Product:* CoverAI, samjho, agent-report-distribution, pharmforge.
- *Software / Backend / Platform:* tenant-api-platform, event-stream-platform, real-time-bidding, stockflow.
- *Data / Analytics:* vibe-odds, E-commerce-Dashboard, ott-content-analytics.
- *Hardware (side-lane):* the six `aditya0si.github.io` labs, clearly labelled.
- *Security / AI-safety:* aegis, Sentinel.

**Honest labelling (critical).** Introduce two badges used consistently: **"Live demo"** (URL returns 200 + marker,
seeded) and **"Engineering case study"** (no URL; the code/tests/benchmarks are the artifact). Never present a
conceptual/spec-stage repo (`PulseGrid`, `architecture.bitnet`, `marketplace`, `mcp-from-scratch`) as a running
product. Several READMEs already model this honesty (`samjho`, `stockflow`, `agent-report-distribution`); make it a
portfolio-wide norm.

---

## 7. Risk register

| Risk | Evidence / where | Mitigation |
|---|---|---|
| **Secrets** | No tracked `.env`/keys found in any candidate (`git ls-files` scan). Deploy-kit never prints secret values. | Keep scans in CI; `gitleaks` already runs in `Portfolio`; add to others. |
| **Committed default secrets** | `portfolio-3pack/02-cadenza` media/auth fall back to a committed literal; reviewer showed a forged token gets 200 (tracked in `MEMORY.md`). | Fail-closed in production; reject committed defaults (fix already dispatched). |
| **Stale deployments** | `schemegpt-api.fly.dev` does not resolve; `DevAtlas` sync failing; `repo-intel`/`INITIAL-AUDIT` stale. | Revision-locked deploys + scheduled liveness (`deployctl status`) that fails on DOWN. |
| **Duplicate provider/local projects** | `CoverAI` exists at `insurance/` **and** `gh-cleanup/CoverAI` (older); `DevAtlas` at `geomap/` **and** `gh-cleanup/DevAtlas`; `Sentinel` at `Sentinal/` and `gh-cleanup/Sentinel`. | Declare canonical path per project (section 2) and remove/ignore `gh-cleanup` clones. |
| **Free-tier sleep/expiry** | Render spins down after 15 min idle; Render PG **expires**; Streamlit sleeps after 12 h; Cloudflare 10 ms CPU/req. | Put state on Neon/Supabase; state cold-start in README; keep edge APIs short. |
| **Databases** | tenant-api, event-stream, grounded, samjho, vibe-odds, DevAtlas need Postgres/Redis/Redpanda; none has a free hosted DB wired. | Standardise on Neon (pgvector) + Upstash (Redis); Redpanda has no free tier → recorded-run demo. |
| **CORS/auth** | schemeGPT proxies API server-side to avoid CORS (good); CoverAI/DevAtlas rely on env `ALLOWED_ORIGINS`; cadenza auth fail-open. | Same-origin proxy pattern; explicit origin allowlists; fail-closed auth. |
| **Seed/demo data** | samjho needs a corpus (licensing forbids shipping textbook text — design); agent-report uses synthetic data; vibe-odds mock mode. | Ship small openly-licensed/demo datasets; label synthetic clearly. |
| **Cost surprises** | Fly.io/AWS/Railway are not free (deploy-kit README correct); agent-report's paid EMR path is off by default; `committed COST.md` reportedly states a superseded free tier (`MEMORY.md` M12). | Free-tier defaults only; put cost notes in each deployed README; re-verify pricing before enabling. |
| **Maintenance burden** | ~30 candidate dirs, several duplicate clones, multiple parallel agent sessions (portfolio-3pack, Cyber, etc.). | Ship 3–10, archive the rest, one canonical path each, one deploy target each. |
| **False-green CI** | deploy-kit runtimes that pass with "nothing ran"; status using any workflow. | Section 5.5 fixes. |

---

## 8. First implementation milestone (1–3 projects)

**Scope:** deploy-kit hygiene + two fastest credible live wins + confirm one flagship. Chosen to be low-risk
(read-mostly, free tier) and to exercise the deploy-kit guarantees on real repos.

**Project A — deploy-kit itself (adoption + correctness)**
1. Fix `ci-static.yml`: vendor `scripts/check_links.py` into scaffolded callers (or `uses:` a deploy-kit checkout).
2. Make `cmd_status` filter by the CI workflow(s).
3. Add `samjho` to `sites.json` with its web marker; add an `api` marker slot for two-tier apps.
4. Gate: `python bin/deployctl.py selftest` → OK; `python bin/deployctl.py status` shows ci + live for every row.
5. Done: a new call in one real repo uses a deploy-kit reusable workflow and produces a verified live URL.

**Project B — E-commerce-Dashboard (Olist BI) → Streamlit Community Cloud**
1. Gate locally: `pip install -r requirements.txt && python -m scripts.pipeline && python -m pytest tests/ -q`; then `streamlit run dashboard/app.py`.
2. Deploy via share.streamlit.io (no secrets); add `homepageUrl` to `aditya0si/E-commerce-Dashboard`.
3. Live marker: a stable KPI string (`R$ 13.22M` / "Overview").
4. CI expectation: add `ci.yml` (Python) via deploy-kit so the suite runs on push.
5. Done: public Streamlit URL renders 6 pages from committed raw data; CI green; manifest row live.

**Project C — CoverAI (confirm live product end-to-end)**
1. Gate locally: run the monorepo suite per `insurance/README.md` (pnpm/turbo + API tests).
2. Probe the live web **and** decide/host the API (Render/Cloudflare + Neon pgvector).
3. Add an API `/health` marker; keep the existing web marker.
4. Done: from the live URL, a reviewer completes one claim lifecycle against a seeded demo; deploy step probes both markers.

**Approval needed before starting:** which CoverAI tree is canonical (`insurance/` vs `gh-cleanup/CoverAI`); whether
to host the CoverAI/samjho/schemeGPT APIs on Render (cold start) vs Cloudflare (CPU limits); and permission to add
`homepageUrl`/CI files to GitHub repos.

---

## 9. Evidence appendix

**Commands run (read-only unless noted).**

```
ls -la C:/Users/oliad/Desktop
ls -la C:/Users/oliad/Desktop/deploy-kit
find deploy-kit -type f -not -path "*/.git/*"
git -C deploy-kit log --oneline -20 ; git remote -v ; git status --short
python bin/deployctl.py selftest
git -C <each project> remote get-url origin ; rev-parse --abbrev-ref HEAD ; log -1
gh repo view <repo> --json defaultBranchRef,homepageUrl,pushedAt,visibility,stargazerCount,primaryLanguage,description
gh run list --repo <repo> --limit 3 --json workflowName,status,conclusion,headBranch,createdAt
# live probes (Python urllib) over deploy-kit/sites.json + samjho + portfolio revision + schemegpt-api.fly.dev + cadenza.vercel.app
# tracked-secret scan: git ls-files | grep -Ei '\.env|secret|credential|\.pem|id_rsa|\.p12'
# adoption scan: grep -rIl "aditya0si/deploy-kit/.github/workflows" ; find . -name check_links.py
find . -maxdepth 3 -name 'vercel.json|netlify.toml|render.y*ml|fly.toml|Procfile|wrangler.*|railway.json'
```

**Files inspected (key):** `deploy-kit/README.md`, `sites.json`, `bin/deployctl.py`, all 10 workflows,
`.netlify/state.json`, `.netlify/netlify.toml`, `scripts/check_links.py`; `SchemeGPT/README.md`,
`SchemeGPT/docs/DEPLOY.md`; `samjho/README.md`; `vibe-odds/README.md`; `tenant-api-platform/README.md`,
`Makefile`; `event-stream-platform/README.md`, `Makefile`; `grounded-knowledge-platform/README.md`, `Makefile`;
`pharmforge/README.md`; `aegis/README.md`; `stockflow/README.md`, `Makefile`; `insurance/README.md`;
`geomap/README.md`; `ecom-dashboard-work/README.md`; `ott-content-analytics/README.md`; `PulseGrid/PulseGrid_README.md`;
`CyberSec/README.md`; `mcp-from-scratch/README.md`; `Portfolio/package.json`, `vercel.json`,
`docs/portfolio/project-inventory.md`, `docs/portfolio/INITIAL-AUDIT.md`, `docs/metrics/deployment-verification.md`;
`repo-intel/REPO_GRADES.md`; `portfolio-3pack/MEMORY.md` and the three project READMEs; selected
`.github/workflows/ci.yml` files for 12 projects.

**Live probe results (today, status + marker).**

```
HTTP 200 cosmos-steller.vercel.app                              marker "Stellar App" OK
HTTP 200 cover-ai-web-adityasinghprojects.vercel.app            marker OK (52568 B)
HTTP 200 aditya0si-live.netlify.app                             marker "Live surfaces" OK
HTTP 200 aditya0si.github.io/{asic-crc-engine,ate-fixture-lab,bom-intelligence,hardware-npi-lab,pcb-dfm-dft,pdn-thermal-lab,si-pi-lab}/   markers OK
HTTP 200 deploy-kit-proof.aditya0si.workers.dev                 marker {"ok":true} OK
HTTP 200 portfolio-gray-five-72.vercel.app                      marker OK (140479 B)
HTTP 200 schemegpt-web-adityasinghprojects.vercel.app           marker OK (17613 B)
HTTP 200 samjho-adityasinghprojects.vercel.app                  200 (19904 B; not in manifest)
HTTP 200 portfolio-cp8t6s5dh-adityasinghprojects.vercel.app     revision URL 200
ERR     schemegpt-api.fly.dev/health                            getaddrinfo failed (host does not resolve)
HTTP 500 cadenza.vercel.app                                     (undocumented guess; not evidence of a deployment)
```

**CI latest-run snapshot (REMOTE, `gh run list`, default branch).**

```
aegis success | CoverAI success | pharmforge success | Sentinel quality-gate success | Cyber success
tenant-api-platform success | event-stream-platform success | grounded ci success + eval success
schemeGPT main success; field-ops branch quality gate failure
samjho ci success, eval failure | portfolio quality gates success
DevAtlas sync workflow failure (2026-09-26) | agent-report success | cadenza success | real-time-bidding success
No runs: vibe-odds, E-commerce-Dashboard, mcp-from-scratch, TheButterFlyEffect, CosmosSteller
No remote: stockflow, marketplace, architecture.bitnet, PulseGrid, ott-content-analytics, llm-robustness-eval, fiver, SIH_PROJECTS
```

No secret values were read or printed. No project repository, Git state, provider, or GitHub object was modified.

---

## Handoff for the parent agent

**Recommended first three actions**
1. **Fix deploy-kit adoption blockers**: vendor/repair `check_links.py` for `ci-static.yml`; make `cmd_status` filter by the CI workflow; add `samjho` (and API markers) to `sites.json`. (Owner: deploy-kit; low risk, free.)
2. **Ship `E-commerce-Dashboard` to Streamlit Community Cloud** — fastest credible live product; gate with `pytest tests/ -q` + `streamlit run dashboard/app.py`; add `ci.yml`.
3. **Confirm CoverAI end-to-end** — verify the live API (not just the HTML marker), seed a demo claim, and host the API on a free tier with a `/health` marker.

**Evidence still missing**
- Whether CoverAI/samjho/schemeGPT **live fronts reach a live backend** (only HTML markers probed).
- Canonical-tree decision for duplicated clones (`insurance/` vs `gh-cleanup/CoverAI`; `geomap/` vs `gh-cleanup/DevAtlas`).
- Local re-execution of test suites for the backend flagships (I inspected config/CI, did not run heavy Docker suites).
- Provider-side state (Vercel/Netlify/Render dashboards) — not accessible read-only here; a Vercel project existing ≠ working deploy.
- `repo-intel` and `INITIAL-AUDIT` timestamps are stale; their "unpublished"/"private" labels conflict with live GitHub metadata.

**Decisions requiring Aditya's approval**
- Which projects form the final top-3 for the first milestone, and the target host per project (Render cold-start vs Cloudflare CPU limits vs Streamlit).
- Permission to modify GitHub repo metadata (`homepageUrl`), add CI files, and create free-tier provider projects.
- Disposition of the `gh-cleanup/` duplicate workspaces and the archive/deprioritize list.
