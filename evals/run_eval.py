"""Measure how accurate the triage engine is on a labelled dataset.

    python -m evals.run_eval                 # uses Claude if ANTHROPIC_API_KEY is set
    TRIAGE_MODE=rules python -m evals.run_eval
    python -m evals.run_eval --min-accuracy 0.8   # exit 1 if below (useful in CI)

Why this matters: an LLM feature without measurement is a guess. This script tells
you, with a number, whether a prompt change made things better or worse.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

from app.config import get_settings
from app.models import IncomingMessage
from app.triage import TriageService

DATASET = Path(__file__).with_name("dataset.jsonl")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    service = TriageService(settings)
    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]

    cat_ok = urg_ok = 0
    confusion: Counter[tuple[str, str]] = Counter()
    engines: Counter[str] = Counter()
    start = time.perf_counter()
    for row in rows:
        msg = IncomingMessage.model_validate(row["input"])
        triage, engine = service.triage(msg)
        engines[engine] += 1
        exp = row["expected"]
        got_cat, got_urg = triage.category.value, triage.urgency.value
        cat_ok += got_cat == exp["category"]
        urg_ok += got_urg == exp["urgency"]
        if got_cat != exp["category"]:
            confusion[(exp["category"], got_cat)] += 1
        if args.verbose or got_cat != exp["category"]:
            mark = "✓" if got_cat == exp["category"] else "✗"
            print(f"{mark} expected={exp['category']:<16} got={got_cat:<16} "
                  f"urgency {exp['urgency']}->{got_urg:<6} | {msg.subject or msg.body[:50]}")

    n = len(rows)
    acc = cat_ok / n
    print("\n=== Results ===")
    print(f"engine(s):          {dict(engines)}")
    print(f"category accuracy:  {cat_ok}/{n} = {acc:.0%}")
    print(f"urgency accuracy:   {urg_ok}/{n} = {urg_ok / n:.0%}")
    print(f"time:               {time.perf_counter() - start:.1f}s")
    if confusion:
        print("most common mistakes (expected -> got):")
        for (e, g), c in confusion.most_common(5):
            print(f"  {e} -> {g}: {c}")
    if acc < args.min_accuracy:
        print(f"FAIL: accuracy {acc:.0%} below threshold {args.min_accuracy:.0%}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
