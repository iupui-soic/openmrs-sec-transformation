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


# Phases used in RQ1 (meeting dates, inclusive).
PHASES = [("Tools and where their output goes", "2026-03-26", "2026-04-23"),
          ("Training and named people", "2026-04-30", "2026-06-11"),
          ("Standing rules", "2026-06-18", "2026-09-03")]


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
    # Phase check for RQ1: passages per meeting, and the same counts over all 120 passages.
    per_meeting = Counter(passages[i]["meeting_date"] for i in ids)
    lines += ["", "## Phase check (RQ1)", "",
              f"Meetings with passages: {len(per_meeting)}; passages per meeting min "
              f"{min(per_meeting.values())}, median {sorted(per_meeting.values())[len(per_meeting) // 2]}, "
              f"max {max(per_meeting.values())}.", "",
              "| Phase | Meetings | Passages | Per meeting | Agreed Decided/Done | Tools (both coders), RQ1 set "
              "| Tools (both coders), all passages | Agreed Decided/Done share |",
              "|---|---|---|---|---|---|---|---|"]
    rq1_set = set(rq1)
    for name, lo, hi in PHASES:
        ph = [i for i in ids if lo <= passages[i]["meeting_date"] <= hi]
        meetings = {passages[i]["meeting_date"] for i in ph}
        dd = [i for i in ph if i in rq1_set]
        tools = lambda s: sum(ch[i]["topic"] == npn[i]["topic"] == "Tools" for i in s)
        lines.append(f"| {name} | {len(meetings)} | {len(ph)} | {len(ph) / len(meetings):.1f} | {len(dd)} "
                     f"| {tools(dd)} of {len(dd)} | {tools(ph)} of {len(ph)} | {len(dd) / len(ph):.0%} |")
    (HERE / "agreement_results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
