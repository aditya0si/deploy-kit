"""Static regression tests: caller-controlled workflow inputs must not be
interpolated directly into shell `run:` bodies while credentials are present.

They must be passed through `env:` and validated before use. These tests are
deliberately text-based so they run without pyyaml on any platform.
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WF = os.path.join(ROOT, ".github", "workflows")

# (workflow file, expression that must not reach a run body, env var it must use)
CASES = [
    ("deploy-cloudflare.yml", "${{ inputs.command }}", "DEPLOY_COMMAND"),
    ("deploy-netlify.yml", "${{ inputs.publish-dir }}", "PUBLISH_DIR"),
    ("ci-static.yml", "${{ inputs.entry }}", "ENTRY"),
]


def read(name):
    with open(os.path.join(WF, name), encoding="utf-8") as fh:
        return fh.read()


def run_bodies(text):
    """Return every shell body belonging to a `run:` step (inline or block)."""
    lines = text.splitlines()
    bodies = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("run:"):
            indent = len(line) - len(line.lstrip())
            block = [line.split("run:", 1)[1]]
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if nxt.strip() == "":
                    block.append("")
                    i += 1
                    continue
                nindent = len(nxt) - len(nxt.lstrip())
                if nindent <= indent:
                    break
                block.append(nxt)
                i += 1
            bodies.append("\n".join(block))
            continue
        i += 1
    return bodies


class InputNotInterpolatedTests(unittest.TestCase):
    def test_flagged_input_never_appears_in_a_run_body(self):
        for name, expr, _var in CASES:
            for body in run_bodies(read(name)):
                self.assertNotIn(expr, body,
                                 "%s interpolates %s into a shell body" % (name, expr))

    def test_flagged_input_is_passed_via_env(self):
        for name, expr, var in CASES:
            self.assertIn("%s: %s" % (var, expr), read(name),
                          "%s does not map %s into env %s" % (name, expr, var))

    def test_each_workflow_invokes_the_validator(self):
        for name, _expr, _var in CASES:
            text = read(name)
            self.assertIn("validate_inputs.py", text,
                          "%s does not validate its caller input" % name)


class CloudflareCommandSafetyTests(unittest.TestCase):
    def setUp(self):
        self.text = read("deploy-cloudflare.yml")

    def test_command_is_enumerated_not_free_form(self):
        self.assertIn("case ", self.text)
        self.assertIn("wrangler@4.141.0 deploy", self.text)
        self.assertIn("wrangler@4.141.0 pages deploy", self.text)

    def test_no_eval_or_shell_c(self):
        self.assertNotIn("eval", self.text.lower())
        self.assertNotIn("sh -c", self.text)

    def test_command_is_validated_before_use(self):
        self.assertIn("wrangler-command", self.text)


class NetlifyAndCiStaticTests(unittest.TestCase):
    def test_publish_dir_is_quoted_when_expanded(self):
        self.assertIn('--dir="$PUBLISH_DIR"', read("deploy-netlify.yml"))

    def test_entry_is_quoted_when_expanded(self):
        text = read("ci-static.yml")
        self.assertIn('"$ENTRY"', text)

    def test_validators_use_the_path_kind(self):
        for name in ("deploy-netlify.yml", "ci-static.yml"):
            self.assertIn("validate_inputs.py\" path", read(name))


if __name__ == "__main__":
    unittest.main()
