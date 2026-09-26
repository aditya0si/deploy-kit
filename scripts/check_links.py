#!/usr/bin/env python3
"""Fail if any local href/src in an HTML file points at something that is not in the tree.

Defaults to the current directory; pass a target directory to scan a caller workspace
while the script itself lives in a separate checkout. Skips absolute paths (deploy
prefixes vary per host) and external/mailto/data/javascript URLs.
"""
import os
import re
import sys

SKIP_PREFIXES = ("http://", "https://", "//", "mailto:", "data:", "javascript:", "tel:")
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "_site", "dist", "build",
             ".deploy-kit-tools"}
ATTR = re.compile("(?:href|src)\\s*=\\s*[\"']([^\"'#?]+)[\"']")


def check(target="."):
    """Return (missing, checked, pages) for the HTML tree rooted at `target`."""
    missing = []
    checked = 0
    pages = 0
    for root, dirs, names in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in names:
            if not name.endswith((".html", ".htm")):
                continue
            pages += 1
            page = os.path.join(root, name)
            try:
                html = open(page, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for attr in ATTR.findall(html):
                if attr.startswith(SKIP_PREFIXES) or attr.startswith("/"):
                    continue
                checked += 1
                candidate = os.path.normpath(os.path.join(root, attr))
                if not os.path.exists(candidate):
                    missing.append(page + " -> " + attr)
    return missing, checked, pages


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    target = args[0] if args else "."
    if not os.path.isdir(target):
        print("::error::not a directory: " + target)
        return 1
    missing, checked, pages = check(target)
    if missing:
        print("::error::broken local links (" + str(len(missing)) + ")")
        for row in missing[:20]:
            print(row)
        return 1
    print("checked " + str(checked) + " local links across " + str(pages) + " pages: all resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
