#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import urllib.request
from datetime import datetime

SOURCE_URL = "https://big.oisd.nl/domainswild2"
OUTPUT_FILE = "oisd-stash.yaml"

def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")

def normalize_and_filter(lines):
    """Lọc các dòng hợp lệ.
    - Bỏ comment (#, //, ;) và dòng trống
    - Bỏ khoảng trắng
    - Giữ nguyên wildcard theo danh sách gốc (nếu có)
    """
    out = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s.startswith("#") or s.startswith("//") or s.startswith(";"):
            continue
        parts = s.split()
        s = parts[-1].strip()

        if s.startswith("||"):
            s = s[2:]
        if s.endswith("^"):
            s = s[:-1]
        if s.startswith("."):
            s = s[1:]

        if s.replace(".", "").isdigit():
            continue
        if "/" in s:
            continue

        out.append(s.lower())
    return sorted(set(out))

def write_yaml(domains, path):
    """Xuất ra YAML theo format:
    payload:
      - 'domain'
    """
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Source: https://big.oisd.nl/domainswild2\n")
        f.write(f"# Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z\n")
        f.write("payload:\n")
        for d in domains:
            f.write(f"  - '{d}'\n")

def main():
    try:
        text = download_text(SOURCE_URL)
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)

    domains = normalize_and_filter(text.splitlines())
    if not domains:
        print("No domains parsed.", file=sys.stderr)
        sys.exit(2)

    write_yaml(domains, OUTPUT_FILE)
    print(f"Wrote {OUTPUT_FILE} with {len(domains)} entries.")

if __name__ == "__main__":
    main()
