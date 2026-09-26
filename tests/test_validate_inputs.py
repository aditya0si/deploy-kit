"""Executable tests for scripts/validate_inputs.py.

Reusable workflows receive caller-controlled strings. Those strings must never be
interpolated directly into a credentialed shell script; they are passed via env and
validated here against a relative-path / enumerated-command contract.
"""
import importlib.util
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "validate_inputs.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_inputs", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RelativePathTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_normal_relative_paths_are_allowed(self):
        for value in ("index.html", ".", "./dist", "dist", "build/site", "a/b/c.html",
                      "My Site/index.html"):
            self.assertEqual(self.mod.validate_relative_path(value), value,
                             "valid path rejected: %r" % value)

    def test_absolute_paths_are_rejected(self):
        for value in ("/etc/passwd", "\\windows", "C:\\Windows", "~/secrets",
                      "/var/www", "\\\\server\\share"):
            with self.assertRaises(ValueError, msg="accepted absolute: %r" % value):
                self.mod.validate_relative_path(value)

    def test_traversal_is_rejected(self):
        for value in ("../secret", "a/../../b", "dist/../../etc", "..", "a/..",
                      "..\\windows", "a\\..\\..\\b"):
            with self.assertRaises(ValueError, msg="accepted traversal: %r" % value):
                self.mod.validate_relative_path(value)

    def test_control_and_newline_characters_are_rejected(self):
        for value in ("a\nb", "a\rb", "a\tb", "a\x00b", "a\x1bb"):
            with self.assertRaises(ValueError, msg="accepted control char: %r" % value):
                self.mod.validate_relative_path(value)

    def test_shell_metacharacters_are_rejected(self):
        for value in ("a;rm -rf /", "a|cat /etc/passwd", "a&&whoami", "a&b",
                      "a$(id)", "a`id`", "a>b", "a<b", "a*b", "a?b", "a[b]",
                      "a{b}", "a(b)", "a'b", 'a"b', "a#b", "a\\b", "a!b"):
            with self.assertRaises(ValueError, msg="accepted metachar: %r" % value):
                self.mod.validate_relative_path(value)

    def test_empty_and_non_string_are_rejected(self):
        for value in ("", None, 5, [], {"x": 1}):
            with self.assertRaises(ValueError, msg="accepted bad type: %r" % value):
                self.mod.validate_relative_path(value)


class WranglerCommandTests(unittest.TestCase):
    def setUp(self):
        self.mod = _load_module()

    def test_supported_commands_map_to_fixed_argv(self):
        self.assertEqual(self.mod.validate_wrangler_command("deploy"), ["deploy"])
        self.assertEqual(self.mod.validate_wrangler_command("pages-deploy"),
                         ["pages", "deploy"])

    def test_arbitrary_commands_are_rejected(self):
        for value in ("rm -rf /", "deploy; rm -rf /", "$(id)", "eval x",
                      "pages deploy", "deploy --flag", "", "publish"):
            with self.assertRaises(ValueError, msg="accepted command: %r" % value):
                self.mod.validate_wrangler_command(value)


class CliTests(unittest.TestCase):
    def _run(self, *args):
        return subprocess.run([sys.executable, SCRIPT] + list(args),
                              capture_output=True, text=True)

    def test_valid_path_exits_zero(self):
        proc = self._run("path", "dist")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_malicious_path_exits_nonzero_without_traceback(self):
        proc = self._run("path", "dist;rm -rf /")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        output = proc.stdout + proc.stderr
        self.assertIn("::error::", output)
        self.assertNotIn("Traceback", output)

    def test_valid_command_exits_zero(self):
        proc = self._run("wrangler-command", "deploy")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_malicious_command_exits_nonzero_without_traceback(self):
        proc = self._run("wrangler-command", "deploy; rm -rf /")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        output = proc.stdout + proc.stderr
        self.assertIn("::error::", output)
        self.assertNotIn("Traceback", output)


if __name__ == "__main__":
    unittest.main()
