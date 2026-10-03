#!/usr/bin/env python3
"""
Block PII / secrets from reaching this public repo.

Two kinds of checks:
  1. Denylist: exact strings that must never appear (account numbers, meter IDs, personal
     emails, internal hostnames...). The list itself is private and is NOT stored here:
       - locally: a file path from `git config pii.denylist` (or --denylist)
       - in CI:   the PII_DENYLIST repository secret (newline-separated)
     Checked in every tracked file, including the bundled notebook assets.
  2. Generic patterns (safe to publish): API keys, private keys, emails, private/Tailscale IPs,
     UK postcodes, MPAN/MPRN-shaped numbers. Checked in our own files only; vendored marimo
     bundles under */assets/ are skipped (minified JS is full of false positives).

Allow a known-safe generic hit by adding `pii-allow` on the same line, or listing
"path:pattern-name" in .github/pii-allowlist.txt.

Exit code 1 if anything is found. Matches are printed redacted, never in full.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

GENERIC = {
    "api-key (sk_live/sk_test)": re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{10,}"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY"),
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "bearer/jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "password assignment": re.compile(r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"\s]{6,}"),
    # lookbehind stops escaped text like "\n@app.cell" (embedded notebook source) matching as "n@app.cell"
    "email address": re.compile(r"(?<![\\\w.%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "private LAN IP": re.compile(r"\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
    "tailscale IP/host": re.compile(r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b|\.ts\.net\b"),
    "UK postcode": re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]? \d[A-Z]{2}\b"),
    "MPAN-like (13 digits)": re.compile(r"(?<![\d.])\d{13}(?![\d.])"),
    "Octopus account no.": re.compile(r"\bA-[0-9A-F]{8}\b"),
}
TEXT_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".json", ".md", ".txt", ".csv", ".py", ".yml", ".yaml",
            ".xml", ".svg", ".webmanifest", ".toml", ".cfg", ".ini", ".sh", ""}
VENDORED = re.compile(r"(^|/)assets/")
SELF = {".github/scripts/pii_scan.py", ".github/pii-allowlist.txt"}


def redact(s: str) -> str:
    s = s.strip()
    return s[:2] + "…" + s[-1:] if len(s) > 4 else "…"


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def load_denylist(path: str | None) -> list[str]:
    raw = os.environ.get("PII_DENYLIST", "")
    if path:
        p = Path(path).expanduser()
        if not p.exists():
            sys.exit(f"pii-scan: denylist file not found: {p}")
        raw += "\n" + p.read_text(encoding="utf-8")
    items = [l.strip() for l in raw.splitlines() if l.strip() and not l.lstrip().startswith("#")]
    return sorted(set(items), key=len, reverse=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--denylist", help="private file of exact strings that must never be published")
    ap.add_argument("--require-denylist", action="store_true", help="fail if no denylist is available")
    args = ap.parse_args()

    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                               check=True).stdout.strip())
    deny = load_denylist(args.denylist)
    if args.require_denylist and not deny:
        print("pii-scan: no denylist available (set PII_DENYLIST or git config pii.denylist)", file=sys.stderr)
        return 1
    deny_lower = [d.lower() for d in deny]

    allow = set()
    al = root / ".github" / "pii-allowlist.txt"
    if al.exists():
        allow = {l.strip() for l in al.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")}

    findings = []
    for rel in tracked_files(root):
        if rel in SELF:
            continue
        path = root / rel
        if Path(rel).suffix.lower() not in TEXT_EXT or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        low = text.lower()
        for d, dl in zip(deny, deny_lower):  # denylist: every file, case-insensitive
            if dl in low:
                findings.append((rel, "denylist", redact(d)))
        if VENDORED.search(rel):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "pii-allow" in line:
                continue
            for name, rx in GENERIC.items():
                m = rx.search(line)
                if m and f"{rel}:{name}" not in allow:
                    findings.append((f"{rel}:{lineno}", name, redact(m.group(0))))

    if findings:
        print(f"pii-scan: {len(findings)} potential PII/secret finding(s) — push blocked:\n", file=sys.stderr)
        for where, kind, snippet in findings[:200]:
            print(f"  {where}  [{kind}]  {snippet}", file=sys.stderr)
        print("\nRemove them, or for a known-safe generic match add `pii-allow` on that line / an entry in "
              ".github/pii-allowlist.txt.", file=sys.stderr)
        return 1
    print(f"pii-scan: clean ({len(deny)} denylist entries, {len(GENERIC)} generic patterns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
