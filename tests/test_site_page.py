"""Executable tests for the generated status page's honesty labels."""
import contextlib
import io
import os
import sys
import tempfile
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

import deployctl  # noqa: E402


class FakeGh:
    def __init__(self, runs=None):
        self.runs = runs or {}

    def __call__(self, args, check=True):
        if args and args[0] == "repo" and "view" in args:
            return {"defaultBranchRef": {"name": "master"}}
        if args and args[0] == "run" and "list" in args:
            wf = args[args.index("--workflow") + 1]
            return list(self.runs.get(wf, []))
        return None


class SitePageTests(unittest.TestCase):
    def _generate(self, sites, runs):
        saved_gh, saved_probe, saved_load = deployctl.gh_json, deployctl.probe, deployctl.load_sites
        deployctl.gh_json = FakeGh(runs)
        deployctl.probe = lambda url, marker=None, **kw: (True, "HTTP 200")
        deployctl.load_sites = lambda: {"sites": sites}
        try:
            td = tempfile.mkdtemp()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                deployctl.cmd_site(types.SimpleNamespace(out=td))
            with open(os.path.join(td, "index.html"), encoding="utf-8") as fh:
                return fh.read(), buf.getvalue()
        finally:
            deployctl.gh_json, deployctl.probe, deployctl.load_sites = saved_gh, saved_probe, saved_load

    def test_partial_site_page_reports_degraded_and_unknown(self):
        sites = [{
            "name": "samjho",
            "repo": "aditya0si/samjho",
            "workflows": ["ci.yml", "eval.yml"],
            "probes": [
                {"url": "https://samjho-adityasinghprojects.vercel.app",
                 "marker": "samjho", "label": "web", "required": True},
                {"label": "api", "required": False},
            ],
        }]
        runs = {"ci.yml": [{"conclusion": "success", "status": "completed", "url": "u"}],
                "eval.yml": [{"conclusion": "failure", "status": "completed", "url": "u"}]}
        page, _ = self._generate(sites, runs)
        self.assertIn("degraded", page.lower())
        self.assertIn("unknown", page.lower())
        self.assertIn("failed", page.lower())

    def test_all_live_site_page_says_live(self):
        sites = [{"name": "ok", "url": "https://ok", "marker": "ok",
                  "repo": "o/r", "workflows": ["ci.yml"]}]
        runs = {"ci.yml": [{"conclusion": "success", "status": "completed", "url": "u"}]}
        page, _ = self._generate(sites, runs)
        summary = page.split('<p class="sub">', 1)[1].split("</p>", 1)[0].lower()
        self.assertIn("fully live", summary)
        self.assertNotIn("degraded", summary)
        self.assertNotIn("partial", summary)
        self.assertNotIn("unknown", summary)


if __name__ == "__main__":
    unittest.main()
