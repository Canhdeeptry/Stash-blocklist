#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import urllib.request
from urllib.parse import urlparse
from datetime import datetime

# ====== cấu hình ======
SOURCE_URLS = [
    # Host/domain lists
    "https://big.oisd.nl/domainswild2",
]
OUT_BLOCK = "oisd-stash.yaml"     # output chặn (payload gồm domain)
OUT_ALLOW = "allowlist.yaml"      # output whitelist (nếu có domain)

# ====== utils tải ======
def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=180) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")

# ====== helpers chung ======
SEPS = "^/*?|"  # các ký tự hay kết thúc phần domain trong ABP

def _take_until_sep(s: str) -> str:
    # Lấy domain đến trước ký tự phân tách
    for i, ch in enumerate(s):
        if ch in SEPS:
            return s[:i]
    return s

def _is_ip_literal(s: str) -> bool:
    # check dạng toàn số và dấu chấm
    return bool(re.fullmatch(r"\d+(?:\.\d+){3}", s))

def _clean_host(h: str) -> str:
    h = h.strip().lower()
    if h.startswith("."):
        h = h[1:]
    # bỏ wildcard đầu
    h = h.lstrip("*.")
    # bỏ phần còn lại nếu có cổng
    h = h.split(":")[0]
    return h

# ====== parser cho ABP ======
def parse_abp(text: str):
    """Trả về (blocked_domains, whitelisted_domains)"""
    blocked, whitelisted = set(), set()
    for raw in text.splitlines():
        line = raw.strip()

        # bỏ rỗng + comment ABP
        if not line or line.startswith(("!", "[Adblock")):
            continue

        # cosmetic / scriptlet / html filters -> bỏ
        if any(tag in line for tag in ("##", "#@#", "#?#", "#$#")):
            continue

        # regex rule /.../ -> bỏ
        if line.startswith("/") and line.endswith("/") and len(line) > 2:
            continue

        is_whitelist = line.startswith("@@")
        if is_whitelist:
            line = line[2:]  # bỏ tiền tố @@ để tái sử dụng logic bên dưới

        host = None

        # Dạng ||example.com^ ...
        if line.startswith("||"):
            rest = line[2:]
            host = _take_until_sep(rest)

        # Dạng |http(s)://host/...
        elif line.startswith("|http"):
            try:
                u = line.lstrip("|")
                host = urlparse(u).hostname
            except Exception:
                host = None

        # Dạng http(s)://host/...
        elif line.startswith(("http://", "https://")):
            try:
                host = urlparse(line).hostname
            except Exception:
                host = None

        # Dạng hostname trần trong ABP (hiếm) -> chọn nếu không có ký tự lạ
        else:
            if re.fullmatch(r"[A-Za-z0-9*_.-]+", line):
                host = line

        if not host:
            continue

        host = _clean_host(host)
        if not host or _is_ip_literal(host) or "." not in host:
            continue

        if is_whitelist:
            whitelisted.add(host)
        else:
            blocked.add(host)

    # loại trùng whitelist > block (ưu tiên cho phép)
    blocked -= whitelisted
    return blocked, whitelisted

# ====== parser cho hostlist/domainlist đơn giản ======
def parse_plain(text: str):
    """Nhận các biến thể: 'domain', '0.0.0.0 domain', '||domain^'..."""
    out = set()
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", ";", "//")):
            continue
        parts = s.split()
        s = parts[-1].strip()

        if s.startswith("||"):
            s = _take_until_sep(s[2:])
        if s.endswith("^"):
            s = s[:-1]
        if s.startswith(("http://", "https://")):
            try:
                host = urlparse(s).hostname or ""
            except Exception:
                host = ""
        else:
            host = s

        host = _clean_host(host)
        if not host or _is_ip_literal(host) or "/" in host or "." not in host:
            continue
        out.add(host)
    return out

# ====== xuất YAML ======
def write_yaml(domains, path, source_note: str):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# Sources:\n{source_note}")
        f.write(f"# Generated: {datetime.utcnow().isoformat(timespec='seconds')}Z\n")
        f.write("payload:\n")
        for d in sorted(domains):
            f.write(f"  - '{d}'\n")

# ====== main ======
def main():
    block_all, allow_all = set(), set()
    source_note_lines = []
    for url in SOURCE_URLS:
        try:
            txt = download_text(url)
            # heuristics: nếu có "##" hoặc dòng bắt đầu "||" nhiều -> ABP
            if "##" in txt or "||" in txt or "[Adblock" in txt:
                b, a = parse_abp(txt)
                block_all |= b
                allow_all |= a
                source_note_lines.append(f"# - {url} (ABP: +{len(b)} block, +{len(a)} allow)")
            else:
                doms = parse_plain(txt)
                block_all |= doms
                source_note_lines.append(f"# - {url} (plain: +{len(doms)} block)")
        except Exception as e:
            source_note_lines.append(f"# - {url} (error: {e})")

    # whitelist thắng block
    block_all -= allow_all

    source_note = "\n".join(source_note_lines) + "\n"

    if block_all:
        write_yaml(block_all, OUT_BLOCK, source_note)
        print(f"Wrote {OUT_BLOCK} with {len(block_all)} entries.")
    else:
        print("Warning: block list empty.", file=sys.stderr)

    if allow_all:
        write_yaml(allow_all, OUT_ALLOW, source_note)
        print(f"Wrote {OUT_ALLOW} with {len(allow_all)} entries.")

if __name__ == "__main__":
    main()
