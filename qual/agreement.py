"""Agreement between the two coders, and the agreed codes used in the paper.

Usage:  python3 qual/agreement.py
Reads   qual/codes_CH.csv, qual/codes_NPN.csv, qual/passages.csv
Writes  qual/agreement_results.md, qual/agreed_rq1.csv, qual/agreed_rq2.csv
Needs only the Python standard library.
"""
import csv
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name):
    with open(HERE / name, newline="", encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def level(effect):
    if effect.startswith("Barrier"):
        return "Barrier"
    if effect.startswith("Enabler"):
        return "Enabler"
    return "Neither"


def kappa(a, b):
    """Cohen's kappa for two equal-length lists of labels."""
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return po, (po - pe) / (1 - pe)


def main():
    ch, npn, passages = load("codes_CH.csv"), load("codes_NPN.csv"), load("passages.csv")
    ids = sorted(ch)
    assert set(ids) == set(npn) == set(passages), "coder files and passages must cover the same ids"

    questions = [
        ("Topic", lambda r: r["topic"]),
        ("Action", lambda r: r["action"]),
        ("Effect: barrier, enabler, or neither", lambda r: level(r["effect"])),
        ("Effect: specific kind", lambda r: r["effect"]),
    ]
    lines = ["# Coder agreement", "",
             f"Passages: {len(ids)}. Coders: CH and NPN, coding independently.", "",
             "| Question | Agreement | Cohen's kappa |", "|---|---|---|"]
    for name, get in questions:
        po, k = kappa([get(ch[i]) for i in ids], [get(npn[i]) for i in ids])
        lines.append(f"| {name} | {po:.1%} | {k:.2f} |")

    # RQ1: passages both coders coded Decided or Done (same value)
    rq1 = [i for i in ids if ch[i]["action"] == npn[i]["action"] and ch[i]["action"] in ("Decided", "Done")]
    # RQ2: passages both coders gave the same barrier or enabler kind
    rq2 = [i for i in ids if ch[i]["effect"] == npn[i]["effect"] and ch[i]["effect"] != "Neither"]

    def topic(i):
        return ch[i]["topic"] if ch[i]["topic"] == npn[i]["topic"] else f"{ch[i]['topic']} / {npn[i]['topic']} (split)"

    for fname, rows, key in [("agreed_rq1.csv", rq1, "action"), ("agreed_rq2.csv", rq2, "effect")]:
        rows = sorted(rows, key=lambda i: (passages[i]["meeting_date"], i))
        with open(HERE / fname, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "meeting_date", key, "topic (CH / NPN if they differ)"])
            for i in rows:
                w.writerow([i, passages[i]["meeting_date"], ch[i][key], topic(i)])

    lines += ["", f"RQ1 set (both coded Decided or Done): {len(rq1)} passages "
              f"{dict(Counter(ch[i]['action'] for i in rq1))}. See agreed_rq1.csv.",
              f"RQ2 set (same barrier or enabler kind): {len(rq2)} passages. See agreed_rq2.csv.", "",
              "| Kind | n |", "|---|---|"]
    for kind, n in sorted(Counter(ch[i]["effect"] for i in rq2).items()):
        lines.append(f"| {kind} | {n} |")
    lines += ["", "Values outside the codebook choices are kept as submitted and count as disagreements: "
              + ", ".join(f"{i} {c}={r[c]}" for i in ids for c, r in [("action", npn[i])]
                          if r[c] not in ("Decided", "Done", "Neither")) + " (NPN)."]
    (HERE / "agreement_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
