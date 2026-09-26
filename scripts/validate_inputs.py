#!/usr/bin/env python3
"""Validate caller-controlled reusable-workflow inputs before they reach a shell.

Reusable workflows receive strings chosen by the caller. Interpolating those strings
straight into a credentialed `run:` script is a shell-injection surface, so workflows
pass them through `env:` and validate them here first.

    validate_inputs.py path <value>              # a normal relative path
    validate_inputs.py wrangler-command <value>  # an allowlisted command -> fixed argv

Paths must be relative (no absolute paths, no `..` traversal, no control characters,
no shell metacharacters). Wrangler commands are an allowlist mapped to fixed argv, so
no free-form shell syntax is ever accepted.
"""
import re
import sys

WRANGLER_COMMANDS = {
    "deploy": ["deploy"],
    "pages-deploy": ["pages", "deploy"],
}

_METACHARS = set(";|&$`<>(){}[]*?!~\"'#\\")
_ALLOWED_PATH = re.compile(r"^[A-Za-z0-9 ._/@+-]+$")
_DRIVE = re.compile(r"^[A-Za-z]:")


def validate_relative_path(value):
    """Return `value` unchanged if it is a safe relative path, else raise ValueError."""
    if not isinstance(value, str) or value == "":
        raise ValueError("path must be a non-empty string")
    for ch in value:
        if ord(ch) < 0x20 or ord(ch) == 0x7F:
            raise ValueError("path must not contain control or newline characters")
        if ch in _METACHARS:
            raise ValueError("path must not contain shell metacharacter %r" % ch)
    if value.startswith(("/", "\\", "~")) or _DRIVE.match(value):
        raise ValueError("path must be relative, not absolute")
    if any(part == ".." for part in re.split(r"[\\/]", value)):
        raise ValueError("path must not contain '..' traversal")
    if not _ALLOWED_PATH.match(value):
        raise ValueError("path contains unsupported characters")
    return value


def validate_wrangler_command(value):
    """Return the fixed argv for an allowlisted command, else raise ValueError."""
    if not isinstance(value, str) or value not in WRANGLER_COMMANDS:
        raise ValueError("command must be one of: " + ", ".join(sorted(WRANGLER_COMMANDS)))
    return list(WRANGLER_COMMANDS[value])


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2 or args[0] not in ("path", "wrangler-command"):
        print("::error::usage: validate_inputs.py {path|wrangler-command} <value>",
              file=sys.stderr)
        return 2
    kind, value = args
    try:
        if kind == "path":
            validate_relative_path(value)
        else:
            validate_wrangler_command(value)
    except ValueError as exc:
        print("::error::invalid %s: %s" % (kind, exc), file=sys.stderr)
        return 1
    print("input ok: %s=%r" % (kind, value))
    return 0


if __name__ == "__main__":
    sys.exit(main())
