"""Config/workflow regression tests (YAML + README text, no execution)."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")

HELPER_REPO = "repository: aditya0si/deploy-kit"


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


def step_blocks(text):
    """Split a workflow into its `- ` step blocks, so a checkout can be inspected alone."""
    blocks, current = [], None
    for line in text.splitlines():
        if re.match(r"^\s*-\s", line):
            if current is not None:
                blocks.append("\n".join(current))
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append("\n".join(current))
    return blocks


class CiStaticTests(unittest.TestCase):
    def setUp(self):
        self.text = read(".github", "workflows", "ci-static.yml")

    def test_caller_checkout_is_preserved(self):
        self.assertIn("actions/checkout@v4", self.text)
        first = self.text.split("actions/checkout@v4", 1)[0]
        self.assertNotIn("repository:", first)

    def test_deploy_kit_is_checked_out_into_namespaced_path(self):
        self.assertIn("repository: aditya0si/deploy-kit", self.text)
        self.assertIn("path:", self.text)
        self.assertIn("deploy-kit-tools", self.text)

    def test_link_checker_runs_from_namespaced_copy_against_caller(self):
        idx = self.text.index("check_links.py")
        window = self.text[idx - 120:idx + 200]
        self.assertIn("github.workspace", window)
        self.assertIn("deploy-kit-tools", window)
        self.assertIn(".", window)


class PinnedCliTests(unittest.TestCase):
    def test_no_latest_anywhere(self):
        for name in os.listdir(WF):
            if name.endswith((".yml", ".yaml")):
                self.assertNotIn("@latest", read(".github", "workflows", name),
                                 "%s still uses @latest" % name)

    def test_vercel_pinned(self):
        self.assertIn("vercel@54.7.1", read(".github", "workflows", "deploy-vercel.yml"))

    def test_netlify_pinned(self):
        self.assertIn("netlify-cli@27.10.0", read(".github", "workflows", "deploy-netlify.yml"))

    def test_wrangler_pinned(self):
        self.assertIn("wrangler@4.141.0", read(".github", "workflows", "deploy-cloudflare.yml"))


class ConcurrencyTests(unittest.TestCase):
    def _has_concurrency(self, name):
        return "concurrency:" in read(".github", "workflows", name)

    def test_all_deploy_jobs_have_concurrency(self):
        for name in ("deploy-vercel.yml", "deploy-netlify.yml", "deploy-cloudflare.yml",
                     "deploy-pages.yml", "docker-ghcr.yml"):
            self.assertTrue(self._has_concurrency(name), "%s lacks concurrency" % name)


class GhcrWordingTests(unittest.TestCase):
    def test_readme_clarifies_ghcr_is_a_registry_not_a_deploy(self):
        text = read("README.md").lower()
        self.assertIn("container image", text)
        self.assertIn("does not deploy", text.replace("does not deploy an application",
                                                      "does not deploy an application"))

    def test_deployctl_clarifies_ghcr(self):
        text = read("bin", "deployctl.py").lower()
        self.assertIn("container image", text)
        self.assertIn("not a deploy", text)


class HelperCheckoutRevisionLockTests(unittest.TestCase):
    """Reusable workflows must run their helper scripts from the same immutable
    revision as the invoked workflow. Checking them out from a mutable branch lets
    a caller pin the workflow to a revision while still executing `main` helpers."""

    FILES = ("ci-static.yml", "deploy-cloudflare.yml", "deploy-netlify.yml")

    def _helper_blocks(self):
        found = []
        for name in self.FILES:
            for block in step_blocks(read(".github", "workflows", name)):
                if HELPER_REPO in block:
                    found.append((name, block))
        return found

    def test_every_reusable_workflow_checks_out_a_deploy_kit_helper(self):
        names = sorted({name for name, _ in self._helper_blocks()})
        self.assertEqual(names, sorted(self.FILES),
                         "each workflow that shells out to deploy-kit helpers must check it out")

    def test_helper_checkout_is_revision_locked_to_the_workflow_sha(self):
        for name, block in self._helper_blocks():
            self.assertIn("ref: ${{ job.workflow_sha }}", block,
                          "%s helper checkout is not pinned to the invoked workflow revision" % name)

    def test_no_helper_checkout_uses_main_or_a_mutable_branch(self):
        for name, block in self._helper_blocks():
            for bad in ("ref: main", "ref: master", "ref: HEAD", "ref: develop",
                        "ref: ${{ github.ref }}"):
                self.assertNotIn(bad, block,
                                 "%s helper checkout uses a mutable ref (%r)" % (name, bad))

    def test_no_workflow_checks_out_deploy_kit_from_main(self):
        for name in os.listdir(WF):
            if not name.endswith((".yml", ".yaml")):
                continue
            text = read(".github", "workflows", name)
            helper = next((b for b in step_blocks(text) if HELPER_REPO in b), None)
            if helper is not None:
                self.assertNotIn("ref: main", helper,
                                 "%s checks out deploy-kit helpers from main" % name)


class CiContractWordingTests(unittest.TestCase):
    def test_readme_documents_per_workflow_contract_and_explicit_unknown(self):
        low = read("README.md").lower()
        self.assertIn("declared workflow", low,
                      "README must state that CI status is the declared workflows' conclusion")
        self.assertIn("no ci declared", low,
                      "README must state that a repo with no declared CI is unknown, never green")


if __name__ == "__main__":
    unittest.main()
