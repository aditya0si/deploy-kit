"""Executable tests for backward-compatible multi-probe site health."""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bin"))

import deployctl  # noqa: E402


def prober_ok(url, marker=None, **kwargs):
    return True, "HTTP 200 + marker"


def prober_fail(url, marker=None, **kwargs):
    return False, "HTTP 404"


class NormalizeProbesTests(unittest.TestCase):
    def test_legacy_url_becomes_required_probe(self):
        probes = deployctl.normalize_probes({"url": "https://x", "marker": "M"})
        self.assertEqual(len(probes), 1)
        self.assertEqual(probes[0]["url"], "https://x")
        self.assertEqual(probes[0]["marker"], "M")
        self.assertTrue(probes[0]["required"])

    def test_probes_list_is_honoured(self):
        site = {"probes": [
            {"url": "https://a", "marker": "A", "label": "web", "required": True},
            {"label": "api", "required": False},
        ]}
        probes = deployctl.normalize_probes(site)
        self.assertEqual([p["label"] for p in probes], ["web", "api"])
        self.assertTrue(probes[0]["required"])
        self.assertFalse(probes[1]["required"])
        self.assertIsNone(probes[1]["url"])

    def test_explicit_empty_probes_does_not_fall_back_to_legacy(self):
        site = {"name": "empty", "url": "https://legacy", "marker": "M", "probes": []}
        self.assertEqual(deployctl.normalize_probes(site), [])

    def test_non_list_probes_raises_explicit_error(self):
        with self.assertRaises(ValueError) as ctx:
            deployctl.normalize_probes({"name": "bad", "probes": "https://x"})
        self.assertIn("probes", str(ctx.exception))
        self.assertNotIn("Traceback", str(ctx.exception))

    def test_non_object_probe_item_raises_explicit_error(self):
        with self.assertRaises(ValueError) as ctx:
            deployctl.normalize_probes({"name": "bad", "probes": ["https://x"]})
        self.assertIn("probe", str(ctx.exception).lower())

    def test_missing_required_defaults_to_true(self):
        probes = deployctl.normalize_probes({"probes": [{"url": "https://x"}]})
        self.assertIs(probes[0]["required"], True)

    def test_boolean_required_is_preserved_exactly(self):
        probes = deployctl.normalize_probes({"probes": [
            {"url": "https://a", "required": True},
            {"url": "https://b", "required": False},
        ]})
        self.assertIs(probes[0]["required"], True)
        self.assertIs(probes[1]["required"], False)

    def test_malformed_required_raises_instead_of_being_coerced(self):
        for value in ("false", "true", "0", 0, 1, 2, None, [], {}, 0.0, ()):
            with self.assertRaises(ValueError,
                                   msg="coerced a non-boolean required=%r" % (value,)):
                deployctl.normalize_probes(
                    {"name": "bad", "probes": [{"url": "https://x", "required": value}]})

    def test_malformed_required_error_names_the_field(self):
        with self.assertRaises(ValueError) as ctx:
            deployctl.normalize_probes({"name": "bad", "probes": [{"required": "false"}]})
        self.assertIn("required", str(ctx.exception))


class EvaluateSiteTests(unittest.TestCase):
    def test_legacy_success_is_live(self):
        res = deployctl.evaluate_site({"name": "legacy", "url": "https://a", "marker": "A"},
                                      prober=prober_ok)
        self.assertEqual(res["health"], "live")

    def test_all_required_success_is_live(self):
        site = {"name": "multi", "probes": [
            {"url": "https://a", "label": "web", "required": True},
            {"url": "https://b", "label": "api", "required": True},
        ]}
        res = deployctl.evaluate_site(site, prober=prober_ok)
        self.assertEqual(res["health"], "live")

    def test_required_failure_is_down(self):
        def selective(url, marker=None, **kwargs):
            return (url == "https://a"), ("ok" if url == "https://a" else "HTTP 500")

        site = {"name": "multi", "probes": [
            {"url": "https://a", "label": "web", "required": True},
            {"url": "https://b", "label": "api", "required": True},
        ]}
        res = deployctl.evaluate_site(site, prober=selective)
        self.assertEqual(res["health"], "down")

    def test_optional_failure_is_degraded(self):
        def selective(url, marker=None, **kwargs):
            return (url == "https://a"), ("ok" if url == "https://a" else "HTTP 500")

        site = {"name": "multi", "probes": [
            {"url": "https://a", "label": "web", "required": True},
            {"url": "https://b", "label": "api", "required": False},
        ]}
        res = deployctl.evaluate_site(site, prober=selective)
        self.assertEqual(res["health"], "degraded")

    def test_optional_unknown_is_degraded(self):
        site = {"name": "samjho", "probes": [
            {"url": "https://a", "label": "web", "required": True},
            {"label": "api", "required": False},
        ]}
        res = deployctl.evaluate_site(site, prober=prober_ok)
        self.assertEqual(res["health"], "degraded")
        states = {p["label"]: p["state"] for p in res["probes"]}
        self.assertEqual(states["api"], "unknown")

    def test_required_unknown_is_unknown(self):
        site = {"name": "x", "probes": [
            {"label": "web", "required": True},
        ]}
        res = deployctl.evaluate_site(site, prober=prober_ok)
        self.assertEqual(res["health"], "unknown")

    def test_no_probes_is_unknown(self):
        res = deployctl.evaluate_site({"name": "x"}, prober=prober_ok)
        self.assertEqual(res["health"], "unknown")

    def test_explicit_empty_probes_is_unknown_not_live(self):
        site = {"name": "empty", "url": "https://a", "marker": "A", "probes": []}
        res = deployctl.evaluate_site(site, prober=prober_ok)
        self.assertEqual(res["health"], "unknown")
        self.assertEqual(res["probes"], [])

    def test_optional_only_pass_is_never_live(self):
        site = {"name": "opt", "probes": [
            {"url": "https://a", "label": "a", "required": False},
            {"url": "https://b", "label": "b", "required": False},
        ]}
        res = deployctl.evaluate_site(site, prober=prober_ok)
        self.assertNotEqual(res["health"], "live")
        self.assertIn(res["health"], ("unknown", "degraded"))

    def test_optional_only_fail_is_never_live(self):
        site = {"name": "opt", "probes": [
            {"url": "https://a", "label": "a", "required": False},
        ]}
        res = deployctl.evaluate_site(site, prober=prober_fail)
        self.assertNotEqual(res["health"], "live")
        self.assertIn(res["health"], ("unknown", "degraded"))

    def test_optional_only_unknown_is_never_live(self):
        site = {"name": "opt", "probes": [
            {"label": "maybe", "required": False},
        ]}
        res = deployctl.evaluate_site(site, prober=prober_ok)
        self.assertNotEqual(res["health"], "live")
        self.assertEqual(res["health"], "unknown")


class RealManifestSamjhoTests(unittest.TestCase):
    def test_samjho_is_degraded_not_live(self):
        with open(os.path.join(ROOT, "sites.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        samjho = next((s for s in data["sites"] if s.get("name") == "samjho"), None)
        self.assertIsNotNone(samjho, "samjho must be in sites.json")
        self.assertIn("samjho-adityasinghprojects.vercel.app", json.dumps(samjho))
        res = deployctl.evaluate_site(samjho, prober=prober_ok)
        self.assertEqual(res["health"], "degraded",
                         "missing optional API must never read as fully live")


if __name__ == "__main__":
    unittest.main()
