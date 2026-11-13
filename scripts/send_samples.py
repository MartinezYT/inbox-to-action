"""Fill a running instance with the sample messages, so the dashboard has data to show.

    python scripts/send_samples.py                         # -> http://localhost:8000
    python scripts/send_samples.py https://your-app.onrender.com --key YOUR_API_KEY
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

DATASET = Path(__file__).resolve().parent.parent / "evals" / "dataset.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", nargs="?", default="http://localhost:8000")
    parser.add_argument("--key", default="", help="value for the X-API-Key header")
    args = parser.parse_args()

    headers = {"X-API-Key": args.key} if args.key else {}
    with httpx.Client(base_url=args.base_url, headers=headers, timeout=60) as client:
        for line in DATASET.read_text().splitlines():
            msg = json.loads(line)["input"]
            r = client.post("/api/messages", json=msg)
            r.raise_for_status()
            t = r.json()["triage"]
            print(f"#{r.json()['id']:<3} {t['category']:<16} {t['urgency']:<6} {msg['subject'] or msg['body'][:40]}")


if __name__ == "__main__":
    main()
