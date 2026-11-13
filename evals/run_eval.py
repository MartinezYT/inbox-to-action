"""Measure how accurate the triage engine is on a labelled dataset.

    python -m evals.run_eval                 # uses Claude if ANTHROPIC_API_KEY is set
    TRIAGE_MODE=rules python -m evals.run_eval
    python -m evals.run_eval --min-accuracy 0.8   # exit 1 if below (useful in CI)
    python -m evals.run_eval --url https://your-app.onrender.com   # test the deployed app (DEMO_MODE on)

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

import httpx

from app.config import get_settings
from app.models import IncomingMessage, Triage
from app.triage import TriageService

DATASET = Path(__file__).with_name("dataset.jsonl")


class RemoteService:
    """Runs the eval against a deployed instance through its /api/try endpoint.

    The API key stays on the server, so you can measure Claude without a key on your laptop.
    /api/try is rate-limited, so on a 429 we wait for the window to reset and retry.
    """

    def __init__(self, base_url: str):
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=90)
        health = self.client.get("/health").json()
        if not health.get("demo_mode"):
            raise SystemExit("That deployment has DEMO_MODE off, so /api/try is unavailable.")
        self.engine = health["engine"]

    def triage(self, msg: IncomingMessage) -> tuple[Triage, str]:
        for _ in range(5):
            r = self.client.post("/api/try", json=msg.model_dump(mode="json"))
            if r.status_code == 429:
                print("  rate limited, waiting 61s...")
                time.sleep(61)
                continue
            r.raise_for_status()
            return Triage.model_validate(r.json()), f"{self.engine} (remote)"
        raise RuntimeError("Still rate limited after 5 tries")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-accuracy", type=float, default=0.0)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--url", help="evaluate a deployed instance instead of running locally")
    args = parser.parse_args()

    service = RemoteService(args.url) if args.url else TriageService(get_settings())
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
