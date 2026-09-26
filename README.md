# deploy-kit

Reusable CI/CD for every repository I ship: one caller workflow per repo, one command from
a local project to a pushed / CI-green / deployed / verified-URL repo, and a manifest that
proves the deployed thing is actually serving.

**Why it exists.** Of 51 public repos, only 3 declare a homepage that actually serves the app.
"Pushed" and "green" were never the hard part — *verified live* is. This kit makes the live
URL a checked artifact instead of a claim.

## Two layers, deliberately separate

| Layer | Mechanism | Cost of a change |
|---|---|---|
| **CI** | reusable workflows in this repo, called by a 5-line `ci.yml` in each project | add a test → one repo |
| **CD** | the platform's own git integration (Vercel / Netlify / Cloudflare Pages / Render auto-deploy on push), or `deploy-*.yml` here when a platform has none | reconnect on the platform |

CI lives in one place because tests change constantly. CD stays on the platform because
git-integration deploys need no token in Actions at all — fewer secrets to rotate, and the
deploy still happens on push.

## Reusable workflows

Callers reference `aditya0si/deploy-kit/.github/workflows/<file>@main`.

| Stack detected by | CI workflow | Deploy workflow |
|---|---|---|
| `go.mod` | `ci-go.yml` | — (container: `docker-ghcr.yml`) |
| `package.json` | `ci-node.yml` | `deploy-vercel.yml` |
| `pyproject.toml` / `requirements.txt` | `ci-python.yml` | `deploy-netlify.yml` or Render blueprint |
| `index.html` only | `ci-static.yml` | `deploy-pages.yml` |
| `Dockerfile` only | — | `docker-ghcr.yml`, `deploy-cloudflare.yml` |

`ci-node.yml` runs install → lint → build → test, and a step whose script does not exist
logs `::notice::` and passes instead of failing (a green run must mean "everything that
exists passed", not "nothing ran"). `ci-static.yml` fails on broken internal links and on
tracked `node_modules` / `.env` / venv paths.

## Free-tier reality (checked Sept 2026)

| Service | Actually free? | Notes that decide placement |
|---|---|---|
| **Vercel Hobby** | yes | personal projects; team `adityasinghprojects` already in use |
| **Netlify Free** | yes, no card | 100 GB bandwidth, 300 build-min/month, functions included. **New sites are created SSO-protected** - visitors get a 401 login redirect until `netlify api updateSite --data '{"site_id":"<id>","body":{"sso_login":false}}'` is run |
| **Cloudflare Workers Free** | yes | 100k req/day, **10 ms CPU per request**, KV/D1/R2 free tiers — edge APIs, not long jobs |
| **GitHub Pages** | yes | static only; already used for the Cisco hardware labs |
| **Render Free** | yes, with teeth | spins down after **15 min idle**, free Postgres **expires** — put durable data on Neon/Supabase, not Render PG |
| **Streamlit Community Cloud** | yes | 1 GB RAM, sleeps after 12 h, one private app |
| **Railway** | **no** | trial = one-time $5, then Hobby $5/month |
| **Fly.io** | **no** | free trial only; usage-billed, card required |
| **AWS** | time-boxed | free-tier credits expire 12 months after account creation; card required; real cost risk if a resource is left running |

So the default free backbone is: **Vercel** (frontends) · **Netlify** (static + functions) ·
**Cloudflare** (edge APIs) · **GitHub Pages** (static/docs) · **Render** (containers that
tolerate a cold start) · **Streamlit** (dashboards). Railway / Fly / AWS get wired only when
a specific project needs them, and the free-tier limits above go in the README of anything
deployed there rather than being implied away.

## Usage

```bash
KIT=~/Desktop/deploy-kit

# new project: scaffold + create repo + push + watch CI
python $KIT/bin/deployctl.py new my-service --desc "what it is" --stack auto --target auto
python $KIT/bin/deployctl.py new my-service --dry-run     # show the plan, write nothing

# existing project: add/refresh the CI caller
python $KIT/bin/deployctl.py ci /c/Users/oliad/Desktop/my-project

# is it actually live? (200 + marker in the body, not just 200)
python $KIT/bin/deployctl.py verify https://app.vercel.app --contains "Dashboard"

# every repo in the manifest: latest CI conclusion + liveness
python $KIT/bin/deployctl.py status

# push local values into repo secrets - values are never printed
python $KIT/bin/deployctl.py secrets my-service --env-file ~/deploy-secrets.txt --all-from-file

python $KIT/bin/deployctl.py selftest      # validate this kit (runs in CI too)
```

## Rules this kit enforces

1. **A 200 is not "live".** Every deploy path ends by fetching the page body and grepping a
   marker. `deploy-vercel.yml` / `deploy-netlify.yml` fail the job when the marker is absent.
2. **The deployed revision is the pushed revision.** CI waits on the run whose `headSha`
   matches local `HEAD`; a responsive old alias is treated as stale.
3. **Secrets never travel through chat or logs.** `secrets` writes with `gh secret set
   --body` and prints key names plus lengths only.
4. **Free-tier limits are stated, not implied.** Anything on Render says "cold start ~30 s";
   anything on Cloudflare says "10 ms CPU ceiling".

## Layout

```
.github/workflows/   reusable CI + deploy workflows (ci-*.yml, deploy-*.yml, docker-ghcr.yml)
bin/deployctl.py     new | ci | verify | status | secrets | selftest
scripts/check_links.py   internal-link gate used by ci-static.yml
sites.json           live surface manifest: name, repo, url, marker
```

## Adding this to an existing repo

Create `.github/workflows/ci.yml`:

```yaml
name: CI
on:
  push:
    branches: [main, master]
  pull_request:
jobs:
  ci:
    uses: aditya0si/deploy-kit/.github/workflows/ci-python.yml@main
```

Then add the badge to the README:
`![CI](https://github.com/aditya0si/<repo>/actions/workflows/ci.yml/badge.svg)`
