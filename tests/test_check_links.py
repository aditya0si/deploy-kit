"""Executable tests for scripts/check_links.py target-directory support.

The checker must be runnable as a reusable tool against a caller workspace,
not only from the directory that happens to contain it.
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_links.py")


def _write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class CheckLinksTests(unittest.TestCase):
    def _run(self, target, cwd=None):
        return subprocess.run([sys.executable, SCRIPT, target], cwd=cwd,
                              capture_output=True, text=True)

    def test_target_argument_passes_for_good_tree(self):
        with tempfile.TemporaryDirectory() as td:
            _write(os.path.join(td, "index.html"), '<a href="page.html">go</a>')
            _write(os.path.join(td, "page.html"), "ok")
            proc = self._run(td, cwd=os.path.dirname(td))
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_target_argument_fails_for_broken_tree(self):
        with tempfile.TemporaryDirectory() as td:
            _write(os.path.join(td, "index.html"), '<a href="missing.html">go</a>')
            proc = self._run(td, cwd=os.path.dirname(td))
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
            self.assertIn("broken local links", proc.stdout)

    def test_default_target_is_cwd(self):
        with tempfile.TemporaryDirectory() as td:
            _write(os.path.join(td, "index.html"), '<img src="gone.png">')
            proc = subprocess.run([sys.executable, SCRIPT], cwd=td,
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)

    def test_target_is_the_only_thing_scanned(self):
        with tempfile.TemporaryDirectory() as parent:
            caller = os.path.join(parent, "caller")
            other = os.path.join(parent, "other")
            os.makedirs(caller)
            os.makedirs(other)
            _write(os.path.join(caller, "index.html"), '<a href="page.html">go</a>')
            _write(os.path.join(caller, "page.html"), "ok")
            _write(os.path.join(other, "index.html"), '<a href="nope.html">bad</a>')
            proc = self._run(caller, cwd=parent)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
