"""Phase 4 support — pseudonymize names to P1..Pn in qual/analysis files (ULTRAPLAN §2/§6.1).

Usage: python3 pseudonymize.py <file> [<file> ...]

Reads data/private/known_names.txt — one person per line, canonical name first,
aliases pipe-separated:  Jane Q. Doe|Jane|jqdoe
All aliases map to the same P-code (mapping persists in data/private/pseudonyms.json,
which never leaves the encrypted volume). Longest aliases replaced first. Files are
rewritten in place; keep originals only under data/private/.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from common import PRIVATE, log, pseudonymize

NAMES_FILE = PRIVATE / "known_names.txt"


def load_aliases():
    if not NAMES_FILE.exists():
        log.error("create %s first (one person per line: Canonical|alias|alias)",
                  NAMES_FILE)
        sys.exit(1)
    pairs = []  # (alias, pcode)
    for line in NAMES_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        pcode = pseudonymize(parts[0])
        for alias in parts:
            pairs.append((alias, pcode))
    return sorted(pairs, key=lambda p: -len(p[0]))  # longest match first


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    pairs = load_aliases()
    for fname in sys.argv[1:]:
        path = Path(fname)
        text = path.read_text()
        n = 0
        for alias, pcode in pairs:
            text, k = re.subn(r"\b%s\b" % re.escape(alias), pcode, text)
            n += k
        path.write_text(text)
        log.info("%s: %d replacements", path, n)


if __name__ == "__main__":
    main()
