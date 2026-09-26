"""Executable tests for workflow-aware, conservative status reporting."""
import contextlib
import io
import json
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

import deployctl  # noqa: E402


class FakeGh:
    """Stands in for deployctl.gh_json with no network."""

    def __init__(self, runs=None, branch="main"):
        self.runs = runs or {}
        self.branch = branch
        self.calls = []

    def __call__(self, args, check=True):
        self.calls.append(list(args))
        if args and args[0] == "repo" and "view" in args:
            return {"defaultBranchRef": {"name": self.branch}}
        if args and args[0] == "run" and "list" in args:
            wf = args[args.index("--workflow") + 1]
            return list(self.runs.get(wf, []))
        return None


def run_row(conclusion=None, status="completed", url="https://run"):
    return {"conclusion": conclusion, "status": status, "url": url}


class AggregateTests(unittest.TestCase):
    def test_empty_is_unknown(self):
        self.assertEqual(deployctl.aggregate_ci([]), "unknown")

    def test_all_success_is_success(self):
        states = [{"state": "success"}, {"state": "success"}]
        self.assertEqual(deployctl.aggregate_ci(states), "success")

    def test_any_failure_is_failed(self):
        states = [{"state": "success"}, {"state": "failed"}]
        self.assertEqual(deployctl.aggregate_ci(states), "failed")

    def test_any_missing_run_is_unknown_never_green(self):
        states = [{"state": "success"}, {"state": "no-run"}]
        self.assertEqual(deployctl.aggregate_ci(states), "unknown")

    def test_pending_is_not_green(self):
        states = [{"state": "success"}, {"state": "pending"}]
        self.assertEqual(deployctl.aggregate_ci(states), "pending")


class WorkflowRunStateTests(unittest.TestCase):
    def test_no_run_is_no_run(self):
        fake = FakeGh({})
        deployctl.gh_json = fake
        try:
            state = deployctl.workflow_run_state("o/r", "ci.yml", "main")
        finally:
            deployctl.gh_json = _ORIG_GH
        self.assertEqual(state["state"], "no-run")

    def test_success_and_failure_mapping(self):
        fake = FakeGh({"ci.yml": [run_row("success")], "eval.yml": [run_row("failure")]})
        deployctl.gh_json = fake
        try:
            ok = deployctl.workflow_run_state("o/r", "ci.yml", "main")
            bad = deployctl.workflow_run_state("o/r", "eval.yml", "main")
        finally:
            deployctl.gh_json = _ORIG_GH
        self.assertEqual(ok["state"], "success")
        self.assertEqual(bad["state"], "failed")


class CiSummaryTests(unittest.TestCase):
    def test_queries_every_declared_workflow(self):
        fake = FakeGh({"ci.yml": [run_row("success")], "eval.yml": [run_row("success")]})
        deployctl.gh_json = fake
        try:
            status, states = deployctl.ci_summary("o/r", "main", ["ci.yml", "eval.yml"])
        finally:
            deployctl.gh_json = _ORIG_GH
        self.assertEqual(status, "success")
        queried = [c[c.index("--workflow") + 1] for c in fake.calls if "run" in c]
        self.assertEqual(queried, ["ci.yml", "eval.yml"])

    def test_missing_run_degrades_to_unknown(self):
        fake = FakeGh({"ci.yml": [run_row("success")]})
        deployctl.gh_json = fake
        try:
            status, _ = deployctl.ci_summary("o/r", "main", ["ci.yml", "eval.yml"])
        finally:
            deployctl.gh_json = _ORIG_GH
        self.assertEqual(status, "unknown")

    def test_no_declared_workflows_is_unknown(self):
        status, _ = deployctl.ci_summary("o/r", "main", [])
        self.assertEqual(status, "unknown")


class CmdStatusTests(unittest.TestCase):
    def _status_json(self, sites, fake, prober=None):
        orig_load = deployctl.load_sites
        saved_gh = deployctl.gh_json
        saved_probe = deployctl.probe
        deployctl.load_sites = lambda: {"sites": sites}
        deployctl.gh_json = fake
        deployctl.probe = prober or (lambda url, marker=None, **kw: (True, "HTTP 200 + marker"))
        try:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                deployctl.cmd_status(types.SimpleNamespace(json=True))
            return json.loads(buf.getvalue())
        finally:
            deployctl.gh_json = saved_gh
            deployctl.probe = saved_probe
            deployctl.load_sites = orig_load

    def test_missing_declaration_is_unknown(self):
        fake = FakeGh({"ci.yml": [run_row("success")]})
        rows = self._status_json([{"name": "x", "repo": "o/r"}], fake)
        self.assertEqual(rows[0]["ci"], "unknown")

    def test_declared_workflow_failure_is_reported(self):
        fake = FakeGh({"ci.yml": [run_row("failure")]})
        rows = self._status_json([{"name": "x", "repo": "o/r", "workflows": ["ci.yml"]}], fake)
        self.assertEqual(rows[0]["ci"], "failed")

    def test_unrelated_latest_workflow_is_not_used(self):
        fake = FakeGh({"ci.yml": [run_row("failure")]})
        rows = self._status_json([{"name": "x", "repo": "o/r", "workflows": ["ci.yml"]}], fake)
        queried = [c[c.index("--workflow") + 1] for c in fake.calls if "run" in c]
        self.assertEqual(queried, ["ci.yml"])
        self.assertEqual(rows[0]["ci"], "failed")

    def test_success_requires_all_declared_workflows(self):
        fake = FakeGh({"ci.yml": [run_row("success")], "eval.yml": [run_row("failure")]})
        rows = self._status_json(
            [{"name": "x", "repo": "o/r", "workflows": ["ci.yml", "eval.yml"]}], fake)
        self.assertEqual(rows[0]["ci"], "failed")


class StatusJsonCompatibilityTests(unittest.TestCase):
    """The old JSON contract exposed `url` and `live`; they must remain, with the
    new `health`, `probes` and `workflows` fields added alongside."""

    def _row(self, site, fake=None, prober=None):
        return CmdStatusTests()._status_json([site], fake or FakeGh({}), prober)[0]

    def test_legacy_fields_are_preserved(self):
        row = self._row({"name": "legacy", "repo": "o/r",
                         "url": "https://a", "marker": "A"})
        for key in ("name", "repo", "ci", "url", "live", "health", "probes", "workflows"):
            self.assertIn(key, row, "missing JSON key %r" % key)
        self.assertEqual(row["url"], "https://a")
        self.assertIsInstance(row["live"], str)
        self.assertTrue(row["live"].startswith("LIVE"), row["live"])

    def test_live_failure_still_reads_down(self):
        row = self._row({"name": "legacy", "repo": "o/r", "url": "https://a"},
                        prober=lambda url, marker=None, **kw: (False, "HTTP 404"))
        self.assertTrue(row["live"].startswith("DOWN"), row["live"])

    def test_site_without_url_keeps_dash_live(self):
        row = self._row({"name": "none", "repo": "o/r"})
        self.assertEqual(row["live"], "-")
        self.assertIsNone(row["url"])

    def test_probes_site_still_exposes_a_url_and_string_live(self):
        row = self._row({"name": "multi", "probes": [
            {"url": "https://a", "label": "web", "required": True},
        ]})
        self.assertIsInstance(row["live"], str)
        self.assertIn("url", row)


class WorkflowDeclarationTypeTests(unittest.TestCase):
    def test_workflow_string_is_accepted(self):
        self.assertEqual(deployctl.site_workflows({"workflows": "ci.yml"}), ["ci.yml"])

    def test_workflow_list_is_accepted(self):
        self.assertEqual(deployctl.site_workflows({"workflows": ["ci.yml", "eval.yml"]}),
                         ["ci.yml", "eval.yml"])

    def test_legacy_singular_workflow_is_accepted(self):
        self.assertEqual(deployctl.site_workflows({"workflow": "ci.yml"}), ["ci.yml"])

    def test_absent_declaration_is_empty(self):
        self.assertEqual(deployctl.site_workflows({"name": "x"}), [])

    def test_non_string_scalar_raises_explicit_error(self):
        with self.assertRaises(ValueError) as ctx:
            deployctl.site_workflows({"name": "x", "workflows": 5})
        self.assertIn("workflows", str(ctx.exception))

    def test_non_string_list_item_raises_explicit_error(self):
        with self.assertRaises(ValueError) as ctx:
            deployctl.site_workflows({"name": "x", "workflows": ["ci.yml", 7]})
        self.assertIn("workflows", str(ctx.exception))


class ManifestWorkflowDeclarationTests(unittest.TestCase):
    """Every repo row must declare its workflows explicitly (possibly empty).

    A silently absent key is indistinguishable from a forgotten one; an explicit
    empty list is a deliberate "no CI here" and must never render as green.
    """

    def _sites(self):
        with open(os.path.join(ROOT, "sites.json"), encoding="utf-8") as fh:
            return json.load(fh)["sites"]

    def _by_name(self):
        return {s.get("name"): s for s in self._sites()}

    def test_every_repo_row_declares_workflows_explicitly(self):
        for site in self._sites():
            if site.get("repo"):
                self.assertIn("workflows", site,
                              "sites.json row %r has a repo but no explicit 'workflows'"
                              % site.get("name"))

    def test_expected_workflow_identities(self):
        by_name = self._by_name()
        cases = {
            "CosmosSteller": [],
            "CoverAI": ["ci.yml"],
            "aditya0si-live": ["self-check.yml"],
            "deploy-kit-proof": ["self-check.yml"],
            "deploy-kit-example": ["ci.yml"],
            "asic-crc-engine": ["ci.yml"],
            "ate-fixture-lab": ["ci.yml"],
            "bom-intelligence": ["ci.yml"],
            "hardware-npi-lab": [],
            "pcb-dfm-dft": ["ci.yml"],
            "pdn-thermal-lab": ["ci.yml"],
            "portfolio": ["ci.yml"],
            "samjho": ["ci.yml", "eval.yml"],
            "schemeGPT": ["ci.yml", "eval.yml"],
            "si-pi-lab": ["ci.yml"],
        }
        for name, expected in cases.items():
            self.assertIn(name, by_name, "sites.json is missing %r" % name)
            self.assertEqual(by_name[name].get("workflows"), expected,
                             "wrong workflow identity for %r" % name)

    def test_schemeGPT_excludes_experimental_generation_eval(self):
        self.assertNotIn("generation-eval.yml",
                         self._by_name()["schemeGPT"].get("workflows", []))

    def test_repo_row_without_declared_ci_is_never_green(self):
        for site in self._sites():
            if site.get("repo") and not site.get("workflows"):
                verdict, _ = deployctl.ci_summary(site["repo"], "main", [])
                self.assertNotEqual(verdict, "success",
                                    "%r declares no CI yet reads green" % site.get("name"))

    def test_explicit_empty_workflows_display_unknown_not_green(self):
        for site in self._sites():
            if site.get("repo") and site.get("workflows") == []:
                rows = CmdStatusTests()._status_json([site], FakeGh({}))
                self.assertEqual(rows[0]["ci"], "unknown",
                                 "%r with explicitly no CI must display unknown"
                                 % site.get("name"))


_ORIG_GH = deployctl.gh_json

if __name__ == "__main__":
    unittest.main()
