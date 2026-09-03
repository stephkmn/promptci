"""Download HumanEval (164 problems) into cases.jsonl.

Usage:
    python examples/humaneval/download.py [--n 164] [--seed 0]

Requires: pip install "promptci[datasets]"

HumanEval_0 is inline in suite.yaml and skipped here. The dataset is small enough
to run in full; use --n for a quick subset while developing the code_exec grader.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
INLINE_IDS = {"HumanEval/0"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=164)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=HERE / "cases.jsonl")
    args = ap.parse_args()

    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SystemExit('pip install "promptci[datasets]" first') from e

    ds = load_dataset("openai/openai_humaneval", split="test")
    print(f"loaded {len(ds)} items; columns: {ds.column_names}")
    rows = [r for r in ds if r["task_id"] not in INLINE_IDS]
    rng = random.Random(args.seed)
    if args.n < len(rows):
        rows = rng.sample(rows, args.n)
    rows.sort(key=lambda r: int(r["task_id"].split("/")[1]))

    with args.out.open("w", encoding="utf-8") as f:
        for r in rows:
            case = {
                "id": r["task_id"].replace("/", "_"),
                "inputs": {
                    "prompt": r["prompt"],
                    "test": r["test"],
                    "entry_point": r["entry_point"],
                },
                "expected": None,
                "tags": ["humaneval"],
            }
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} cases to {args.out}")


if __name__ == "__main__":
    main()
