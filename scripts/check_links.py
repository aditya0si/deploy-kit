#!/usr/bin/env python3
"""Fail if any local href/src in an HTML file points at something that is not in the tree.

Run from the site root. Skips absolute paths (deploy prefixes vary per host) and
external/mailto/data/javascript URLs.
"""
import os
import re
import sys

SKIP_PREFIXES = ("http://", "https://", "//", "mailto:", "data:", "javascript:", "tel:")
SKIP_DIRS = {".git", "node_modules", "venv", ".venv", "_site", "dist", "build"}
ATTR = re.compile("(?:href|src)\\s*=\\s*[\"']([^\"'#?]+)[\"']")

missing = []
checked = 0
pages = 0

for root, dirs, names in os.walk("."):
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
        for target in ATTR.findall(html):
            if target.startswith(SKIP_PREFIXES) or target.startswith("/"):
                continue
            checked += 1
            candidate = os.path.normpath(os.path.join(root, target))
            if not os.path.exists(candidate):
                missing.append(page + " -> " + target)

if missing:
    print("::error::broken local links (" + str(len(missing)) + ")")
    for row in missing[:20]:
        print(row)
    sys.exit(1)

print("checked " + str(checked) + " local links across " + str(pages) + " pages: all resolve")
