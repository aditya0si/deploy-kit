#!/usr/bin/env python3
"""deployctl - one command from a local project to a pushed, deployed, verified, CI-green repo.

Stdlib only. Drives `git` and `gh`; never prints secret values.

    deployctl new  <name> [--stack auto|node|python|go|static|docker]
                          [--target auto|vercel|netlify|cloudflare|pages|render|none]
                          [--path DIR] [--desc TEXT] [--private] [--dry-run] [--no-wait]
    deployctl ci   [PATH]              add/refresh the reusable CI caller in an existing repo
    deployctl verify URL --contains MARKER [--timeout N] [--retries N]
    deployctl status [--json]
    deployctl secrets <repo> --from-env K1,K2    or  --env-file PATH
    deployctl selftest
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

OWNER = "aditya0si"
KIT_SLUG = OWNER + "/deploy-kit"
KIT_BRANCH = "main"
KIT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES = os.path.join(KIT_ROOT, "sites.json")
RAW_BASE = "https://raw.githubusercontent.com/" + KIT_SLUG + "/" + KIT_BRANCH

DRY = False          # set by `new --dry-run`: report the plan, touch nothing

# stack -> (ci workflow file, deploy workflow file or None)
STACKS = {
    "node": ("ci-node.yml", "deploy-vercel.yml"),
    "python": ("ci-python.yml", "deploy-netlify.yml"),
    "go": ("ci-go.yml", None),
    "static": ("ci-static.yml", "deploy-pages.yml"),
    "docker": (None, "docker-ghcr.yml"),
}
# target -> (deploy workflow file, needs secrets, needs a manual click)
TARGETS = {
    "vercel": ("deploy-vercel.yml", ["VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"], False),
    "netlify": ("deploy-netlify.yml", ["NETLIFY_AUTH_TOKEN", "NETLIFY_SITE_ID"], False),
    "cloudflare": ("deploy-cloudflare.yml", ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"], False),
    "pages": ("deploy-pages.yml", [], False),
    "render": (None, [], True),
    "ghcr": ("docker-ghcr.yml", [], False),
    "none": (None, [], False),
}

MIT = """MIT License

Copyright (c) {year} Aditya Singh

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

DEPENDABOT = """version: 2
updates:
  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
  - package-ecosystem: {eco}
    directory: "/"
    schedule:
      interval: weekly
    open-pull-requests-limit: 5
"""

ECO = {"node": "npm", "python": "pip", "go": "gomod", "static": "npm", "docker": "docker"}


# ----------------------------------------------------------------- helpers
def die(msg, code=1):
    print("ERROR: " + msg, file=sys.stderr)
    raise SystemExit(code)


def run(cmd, cwd=None, check=True):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", shell=isinstance(cmd, str))
    if check and proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-6:]
        die("command failed (%d): %s\n%s" % (proc.returncode, cmd if isinstance(cmd, str) else " ".join(cmd),
                                            "\n".join(tail)))
    return proc


def out(cmd, cwd=None, check=True):
    return run(cmd, cwd=cwd, check=check).stdout.strip()


def gh_json(args, check=True):
    txt = out(["gh"] + args, check=check)
    if not txt:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        die("unexpected gh output: " + txt[:200])


def write_if_changed(path, content):
    content = content.replace("\r\n", "\n")
    if DRY:
        return True
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            if fh.read().replace("\r\n", "\n") == content:
                return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
    return True


def in_repo(path):
    proc = run(["git", "rev-parse", "--show-toplevel"], cwd=path, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def default_branch(path):
    return out(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=path, check=False) or "main"


def remote_url(path):
    proc = run(["git", "remote", "get-url", "origin"], cwd=path, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def head_sha(path):
    return out(["git", "rev-parse", "HEAD"], cwd=path, check=False)


# ----------------------------------------------------------------- detection
def detect_stack(path):
    has = lambda *names: any(os.path.exists(os.path.join(path, n)) for n in names)
    if has("go.mod"):
        return "go"
    if has("package.json"):
        return "node"
    if has("pyproject.toml", "requirements.txt", "setup.py", "main.py"):
        return "python"
    if has("index.html"):
        return "static"
    if has("Dockerfile"):
        return "docker"
    return None


def detect_pm(path):
    if os.path.exists(os.path.join(path, "pnpm-lock.yaml")):
        return "pnpm"
    if os.path.exists(os.path.join(path, "yarn.lock")):
        return "yarn"
    return "npm"


def default_target(stack, path):
    if stack == "node":
        pkg = os.path.join(path, "package.json")
        try:
            deps = json.load(open(pkg, encoding="utf-8")).get("dependencies", {})
        except Exception:
            deps = {}
        return "vercel" if deps else "pages"
    if stack == "static":
        return "pages"
    if stack == "docker":
        return "ghcr"
    return "render"          # python / go services: blueprint + one dashboard click


# ----------------------------------------------------------------- scaffolding
def ci_caller(stack, pm="npm", entry="index.html", workdir="."):
    ci_file = STACKS[stack][0]
    ref = "%s/.github/workflows/%s@%s" % (KIT_SLUG, ci_file, KIT_BRANCH)
    inputs = []
    if stack == "node":
        if workdir != ".":
            inputs = [("working-directory", workdir)]
    elif stack == "static":
        if entry != "index.html":
            inputs.append(("entry", entry))
        if workdir != ".":
            inputs.append(("working-directory", workdir))
    elif stack == "python" and workdir != ".":
        inputs = [("working-directory", workdir)]
    elif stack == "go" and workdir != ".":
        inputs = [("working-directory", workdir)]

    body = ["name: CI", "", "on:", "  push:", "    branches: [main, master]", "  pull_request:",
            "  workflow_dispatch:", "", "jobs:", "  ci:", "    uses: " + ref]
    if inputs:
        body.append("    with:")
        for key, val in inputs:
            body.append("      %s: %s" % (key, json.dumps(val)))
    return "\n".join(body) + "\n"


def deploy_caller(target, marker=None, extra=None):
    file_name = TARGETS[target][0]
    if not file_name:
        return None
    ref = "%s/.github/workflows/%s@%s" % (KIT_SLUG, file_name, KIT_BRANCH)
    secrets = TARGETS[target][1]
    body = ["name: Deploy", "", "on:", "  push:", "    branches: [main, master]",
            "  workflow_dispatch:", "", "jobs:", "  deploy:", "    uses: " + ref]
    opts = dict(extra or {})
    if marker:
        if target in ("vercel", "netlify"):     # only these declare the input
            opts["verify-marker"] = marker
        else:
            print("note: target %s has no verify-marker input - marker ignored" % target)
    if opts:
        body.append("    with:")
        for key, val in opts.items():
            body.append("      %s: %s" % (key, json.dumps(val)))
    if secrets:
        body.append("    secrets:")
        for s in secrets:
            body.append("      %s: ${{ secrets.%s }}" % (s, s))
    return "\n".join(body) + "\n"


def ensure_gitignore(path, stack):
    gi = os.path.join(path, ".gitignore")
    want = {
        "node": ["node_modules/", ".next/", "dist/", "build/", ".env", ".env.*", "*.log", ".vercel/"],
        "python": ["__pycache__/", "*.pyc", ".venv/", "venv/", "*.egg-info/", ".pytest_cache/", ".env", "*.log"],
        "go": ["*.exe", "*.test", "*.out", "/bin/", ".env", "*.log"],
        "static": [".DS_Store", "Thumbs.db", "*.log"],
        "docker": [".env", "*.log"],
    }.get(stack, [".env", "*.log"])
    existing = ""
    if os.path.exists(gi):
        existing = open(gi, encoding="utf-8", errors="replace").read()
    missing = [line for line in want if line not in existing.split()]
    if not missing:
        return False
    if DRY:
        return True
    block = ("\n" if existing and not existing.endswith("\n") else "") + "\n".join(missing) + "\n"
    with open(gi, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(existing + block)
    return True


def ensure_readme(path, name, desc, stack, target, has_ci=True):
    readme = os.path.join(path, "README.md")
    badge = ("![CI](https://github.com/%s/%s/actions/workflows/ci.yml/badge.svg)" % (OWNER, name)
             if has_ci else "")
    if not os.path.exists(readme):
        bits = ["# " + name, ""]
        if badge:
            bits += [badge, ""]
        bits += [desc or "TODO: one paragraph on what this is and why.",
                 "", "_Stack: %s. Target: %s._" % (stack, target)]
        if not DRY:
            write_if_changed(readme, "\n".join(bits) + "\n")
        return
    if not badge:
        return
    text = open(readme, encoding="utf-8", errors="replace").read()
    if "actions/workflows/ci.yml/badge.svg" in text:
        return
    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        lines[1:1] = ["", badge]
    else:
        lines[0:0] = [badge, ""]
    if not DRY:
        write_if_changed(readme, "\n".join(lines) + "\n")


def scaffold(path, name, desc, stack, target, marker=None):
    """Returns list of (path, changed)."""
    changed = []
    caller = os.path.join(path, ".github", "workflows", "ci.yml")
    if STACKS[stack][0]:
        changed.append((caller, write_if_changed(caller, ci_caller(stack, detect_pm(path)))))
    dep = deploy_caller(target, marker=marker)
    if dep:
        dpath = os.path.join(path, ".github", "workflows", "deploy.yml")
        changed.append((dpath, write_if_changed(dpath, dep)))
    changed.append((os.path.join(path, ".gitignore"), ensure_gitignore(path, stack)))
    eco = ECO.get(stack)
    if eco:
        changed.append((os.path.join(path, ".github", "dependabot.yml"),
                        write_if_changed(os.path.join(path, ".github", "dependabot.yml"),
                                         DEPENDABOT.format(eco=eco))))
    lic = os.path.join(path, "LICENSE")
    if not os.path.exists(lic):
        changed.append((lic, write_if_changed(lic, MIT.format(year=time.strftime("%Y")))))
    ensure_readme(path, name, desc, stack, target, has_ci=bool(STACKS[stack][0]))
    return changed


# ----------------------------------------------------------------- sites.json
def load_sites():
    if not os.path.exists(SITES):
        return {"sites": []}
    with open(SITES, encoding="utf-8") as fh:
        return json.load(fh)


def save_sites(data):
    with open(SITES, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def upsert_site(name, url=None, repo=None, marker=None):
    data = load_sites()
    row = next((s for s in data["sites"] if s.get("name") == name), None)
    if row is None:
        row = {"name": name}
        data["sites"].append(row)
    if url:
        row["url"] = url
    if repo:
        row["repo"] = repo
    if marker:
        row["marker"] = marker
    data["sites"].sort(key=lambda s: s.get("name", ""))
    save_sites(data)
    return row


def probe(url, marker=None, timeout=20.0, retries=3):
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "deployctl/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                if resp.status != 200:
                    last = "HTTP %s" % resp.status
                elif marker and marker not in body:
                    last = "HTTP 200 but marker %r missing" % marker
                else:
                    return True, "HTTP 200" + (" + marker" if marker else "") + " (%d bytes)" % len(body)
        except urllib.error.HTTPError as exc:
            last = "HTTP %s" % exc.code
        except Exception as exc:                                   # noqa: BLE001
            last = type(exc).__name__ + ": " + str(exc)[:80]
        if attempt < retries - 1:
            time.sleep(3)
    return False, last


# ----------------------------------------------------------------- commands
def cmd_new(args):
    path = os.path.abspath(args.path or os.getcwd())
    if not os.path.isdir(path):
        die("not a directory: " + path)
    if remote_url(path) and not args.force:
        die("origin already set (%s) - use `deployctl ci` for an existing repo" % remote_url(path))

    stack = args.stack if args.stack != "auto" else detect_stack(path)
    if not stack:
        die("could not detect a stack (no go.mod/package.json/pyproject/index.html/Dockerfile)")
    target = args.target if args.target != "auto" else default_target(stack, path)
    if target not in TARGETS:
        die("unknown target: " + target)

    global DRY
    DRY = bool(args.dry_run)
    print("project : %s" % path)
    print("stack   : %s" % stack)
    print("target  : %s" % target)
    verb = "would write" if DRY else "written"
    scaffolded = scaffold(path, args.name, args.desc, stack, target, args.marker)
    for path_, changed in scaffolded:
        print("  %-52s %s" % (os.path.relpath(path_, path), verb if changed else "unchanged"))
    expected = [os.path.basename(p) for p, _ in scaffolded
                if os.path.basename(os.path.dirname(p)) == "workflows"]

    if args.dry_run:
        print("\nDRY RUN - nothing created, nothing pushed.")
        print("would run: git init (if needed) && git add -A && git commit")
        print("would run: gh repo create %s/%s --%s --source . --push"
              % (OWNER, args.name, "private" if args.private else "public"))
        return 0

    if not in_repo(path):
        run(["git", "init", "-b", "main"], cwd=path)
        print("git: initialised on main")

    run(["git", "add", "-A"], cwd=path)
    if run(["git", "diff", "--cached", "--quiet"], cwd=path, check=False).returncode != 0:
        run(["git", "-c", "user.name=Aditya Singh", "-c", "user.email=oliaditya05@gmail.com",
             "commit", "-m", "chore: project scaffolding + CI"], cwd=path)
        print("git: committed scaffolding")

    visibility = "--private" if args.private else "--public"
    desc = args.desc or ("%s - %s project" % (args.name, stack))
    run(["gh", "repo", "create", "%s/%s" % (OWNER, args.name), visibility, "--source", ".",
         "--remote", "origin", "--push", "--description", desc], cwd=path)
    print("github: created %s/%s and pushed" % (OWNER, args.name))

    sha = head_sha(path)
    upsert_site(args.name, repo="%s/%s" % (OWNER, args.name))
    if not args.no_wait:
        if not watch_ci(args.name, sha, expected):
            print("RESULT: pushed, but CI is NOT green - fix before calling this done")
            return 1
        print("RESULT: pushed and CI green")
    print_platform_next_steps(args.name, target, stack)
    return 0


def print_platform_next_steps(name, target, stack):
    secrets = TARGETS[target][1]
    print("\nnext steps for %s:" % target)
    if target == "vercel":
        print("  vercel link --yes --scope adityasinghprojects --project %s   # then set VERCEL_ORG_ID/PROJECT_ID" % name)
    elif target == "netlify":
        print("  netlify sites:create --name %s   # then: deployctl secrets %s --env-file <file>" % (name, name))
    elif target == "cloudflare":
        print("  wrangler deploy   # then add CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID as repo secrets")
    elif target == "pages":
        print("  gh api -X POST repos/%s/%s/pages -f 'source[branch]=main' -f 'source[path]=/'" % (OWNER, name))
    elif target == "render":
        print("  commit render.yaml, then Render dashboard -> New -> Blueprint -> pick %s -> Apply" % name)
    if secrets:
        print("  required repo secrets: %s" % ", ".join(secrets))
        print("  set them with: deployctl secrets %s --env-file <path-to-secrets-file>" % name)


def watch_ci(repo, sha, wf_files, timeout_s=900):
    """Wait for the CI/deploy workflows for THIS sha. Success only if every expected
    workflow has a completed, successful run - Dependabot and other workflows are ignored,
    and a workflow with no observed run counts as failure, never as success."""
    wf_files = [w for w in wf_files] or []
    if not wf_files:
        print("ci: no workflows expected for this project")
        return True
    print("ci: waiting for %s on %s..." % (",".join(wf_files), sha[:8]))
    deadline = time.time() + timeout_s
    final = {}
    while True:
        final = {}
        for wf in wf_files:
            runs = gh_json(["run", "list", "--repo", "%s/%s" % (OWNER, repo), "--workflow", wf,
                            "--limit", "15",
                            "--json", "databaseId,headSha,status,conclusion,event,url"], check=False) or []
            mine = [r for r in runs if r.get("headSha") == sha]
            push_runs = [r for r in mine if r.get("event") == "push"]
            pick = (push_runs or mine or [None])[0]
            if pick:
                final[wf] = pick
        pending = [w for w in wf_files if w not in final or final[w].get("status") != "completed"]
        if not pending or time.time() > deadline:
            break
        time.sleep(12)

    ok = True
    for wf in wf_files:
        run = final.get(wf)
        if not run:
            print("ci: %-11s NO RUN OBSERVED for %s -> treated as failure" % (wf, sha[:8]))
            ok = False
            continue
        verdict = "success" if run.get("conclusion") == "success" else str(run.get("conclusion") or run.get("status"))
        print("ci: %-11s %-9s %s" % (wf, verdict, run.get("url")))
        if verdict != "success":
            ok = False
    return ok


def cmd_ci(args):
    path = os.path.abspath(args.path or os.getcwd())
    if not in_repo(path):
        die("not a git repository: " + path)
    stack = args.stack if args.stack != "auto" else detect_stack(path)
    if not stack or not STACKS[stack][0]:
        die("no reusable CI for stack: %s" % stack)
    caller = os.path.join(path, ".github", "workflows", "ci.yml")
    changed = write_if_changed(caller, ci_caller(stack, detect_pm(path)))
    print("%s: %s" % (os.path.relpath(caller, path), "written" if changed else "already current"))
    if changed:
        print("commit and push to activate it.")
    return 0


def cmd_verify(args):
    ok, detail = probe(args.url, args.contains, timeout=args.timeout, retries=args.retries)
    print(("OK   " if ok else "FAIL ") + args.url + " - " + detail)
    return 0 if ok else 1


def default_branch_of(repo):
    info = gh_json(["repo", "view", repo, "--json", "defaultBranchRef"], check=False)
    try:
        return info["defaultBranchRef"]["name"]
    except Exception:                                              # noqa: BLE001
        return "main"


def cmd_status(args):
    sites = load_sites().get("sites", [])
    if not sites and not args.json:
        print("sites.json is empty - add entries with `deployctl new` or upsert_site()")
    rows = []
    for site in sites:
        repo = site.get("repo")
        ci = "-"
        if repo:
            branch = default_branch_of(repo)
            runs = gh_json(["run", "list", "--repo", repo, "--limit", "1", "--branch", branch,
                            "--json", "conclusion,status,url"], check=False) or []
            if runs:
                r = runs[0]
                ci = (r.get("conclusion") or r.get("status") or "?")
                if ci == "failure":
                    ci = "FAILED"
        live = "-"
        if site.get("url"):
            ok, detail = probe(site["url"], site.get("marker"), retries=1, timeout=15)
            live = ("LIVE " + detail) if ok else ("DOWN " + detail)
        rows.append({"name": site.get("name"), "repo": repo, "ci": ci,
                     "url": site.get("url"), "live": live})
    if args.json:
        print(json.dumps(rows, indent=2))
        return 0
    width = max([len(r["name"] or "") for r in rows] + [4])
    print("%-*s  %-9s  %s" % (width, "site", "ci", "live"))
    print("-" * (width + 40))
    for r in rows:
        print("%-*s  %-9s  %s" % (width, r["name"], r["ci"], r["live"]))
    return 0


def cmd_secrets(args):
    keys = [k.strip() for k in (args.from_env or "").split(",") if k.strip()]
    if args.env_file:
        file_keys = []
        with open(args.env_file, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                file_keys.append(key.strip())
                os.environ[key.strip()] = val.strip().strip('"').strip("'")
        if args.all_from_file:
            keys = list(dict.fromkeys(file_keys))
    if not keys:
        die("nothing to set: pass --from-env K1,K2 or --env-file PATH")
    for key in keys:
        val = os.environ.get(key)
        if not val:
            print("skip %s (not in environment)" % key)
            continue
        run(["gh", "secret", "set", key, "--repo", "%s/%s" % (OWNER, args.repo),
             "--body", val])
        print("set %s on %s/%s (%d chars)" % (key, OWNER, args.repo, len(val)))
    return 0


def cmd_selftest(args):
    try:
        import yaml
        from yaml.constructor import ConstructorError
    except ImportError:
        die("pyyaml required for selftest (pip install pyyaml)")

    class Strict(yaml.SafeLoader):
        pass

    def no_dup(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ConstructorError(None, None, "duplicate key %r" % (key,), key_node.start_mark)
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dup)

    wf_dir = os.path.join(KIT_ROOT, ".github", "workflows")
    problems, checked = [], 0
    for name in sorted(os.listdir(wf_dir)):
        if not name.endswith((".yml", ".yaml")):
            continue
        checked += 1
        try:
            doc = yaml.load(open(os.path.join(wf_dir, name), encoding="utf-8"), Loader=Strict)
        except Exception as exc:                                   # noqa: BLE001
            problems.append("%s: %s" % (name, str(exc).splitlines()[0]))
            continue
        on_key = doc.get("on", doc.get(True))
        if not isinstance(on_key, dict):
            problems.append("%s: no trigger mapping" % name)
            continue
        if name != "self-check.yml" and "workflow_call" not in on_key:
            problems.append("%s: missing workflow_call" % name)
        if not doc.get("jobs"):
            problems.append("%s: no jobs" % name)

    for stack, (ci_file, _) in STACKS.items():
        if ci_file and not os.path.exists(os.path.join(wf_dir, ci_file)):
            problems.append("stack %s -> missing %s" % (stack, ci_file))
    for target, (deploy_file, _, _) in TARGETS.items():
        if deploy_file and not os.path.exists(os.path.join(wf_dir, deploy_file)):
            problems.append("target %s -> missing %s" % (target, deploy_file))

    linker = os.path.join(KIT_ROOT, "scripts", "check_links.py")
    if not os.path.exists(linker):
        problems.append("scripts/check_links.py missing")
    else:
        import py_compile
        try:
            with tempfile.TemporaryDirectory() as td:
                py_compile.compile(linker, doraise=True, cfile=os.path.join(td, "check_links.pyc"))
        except Exception as exc:                                   # noqa: BLE001
            problems.append("check_links.py does not compile: %s" % exc)
    try:
        json.load(open(SITES, encoding="utf-8"))
    except Exception as exc:                                       # noqa: BLE001
        problems.append("sites.json invalid: %s" % exc)

    print("workflows checked: %d" % checked)
    print("stacks: %s" % ",".join(sorted(STACKS)))
    print("targets: %s" % ",".join(sorted(TARGETS)))
    if problems:
        for p in problems:
            print("::error::" + p)
        return 1
    print("selftest: OK")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="deployctl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new", help="scaffold, create the repo, push, watch CI")
    p.add_argument("name")
    p.add_argument("--path", default=None)
    p.add_argument("--stack", default="auto", choices=["auto"] + sorted(STACKS))
    p.add_argument("--target", default="auto", choices=["auto"] + sorted(TARGETS))
    p.add_argument("--desc", default=None)
    p.add_argument("--private", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-wait", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--marker", default=None, help="string the live page must contain")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("ci", help="add/refresh the CI caller workflow")
    p.add_argument("path", nargs="?", default=None)
    p.add_argument("--stack", default="auto", choices=["auto"] + sorted(STACKS))
    p.set_defaults(func=cmd_ci)

    p = sub.add_parser("verify", help="probe a URL for 200 + marker")
    p.add_argument("url")
    p.add_argument("--contains", default=None)
    p.add_argument("--timeout", type=float, default=20.0)
    p.add_argument("--retries", type=int, default=3)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("status", help="CI + liveness for every site in sites.json")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("secrets", help="push local env values into repo secrets (never printed)")
    p.add_argument("repo")
    p.add_argument("--from-env", default=None)
    p.add_argument("--env-file", default=None)
    p.add_argument("--all-from-file", action="store_true")
    p.set_defaults(func=cmd_secrets)

    p = sub.add_parser("selftest", help="validate this kit")
    p.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
