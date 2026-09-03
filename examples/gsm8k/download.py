"""Download a GSM8K test subset into cases.jsonl.

Usage:
    python examples/gsm8k/download.py --n 200 --seed 0

Requires the `datasets` library: pip install "promptci[datasets]"

Why a fixed seed and a committed item list: the 200 items you evaluate on are part
of the experimental setup. Two runs are only comparable if they used the same
items. The script writes `cases.jsonl` (not committed, 200 rows) and
`case_ids.txt` (committed, just the ids) so anyone can reproduce the exact subset.

The five items with indices 0-4 are inline in suite.yaml and are skipped here so
there are no duplicate ids.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
INLINE_INDICES = {0, 1, 2, 3, 4}
ANSWER_RE = re.compile(r"####\s*(-?[\d,]*\.?\d+)")


def final_answer(answer_text: str) -> str:
    m = ANSWER_RE.search(answer_text)
    if not m:
        raise ValueError(f"no '#### N' in reference answer: {answer_text[-80:]!r}")
    return m.group(1).replace(",", "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=HERE / "cases.jsonl")
    args = ap.parse_args()

    try:
        from datasets import load_dataset
    except ImportError as e:
        raise SystemExit('pip install "promptci[datasets]" first') from e

    ds = load_dataset("openai/gsm8k", "main", split="test")
    print(f"loaded {len(ds)} test items; columns: {ds.column_names}")
    indices = [i for i in range(len(ds)) if i not in INLINE_INDICES]
    rng = random.Random(args.seed)
    chosen = sorted(rng.sample(indices, args.n))

    with args.out.open("w", encoding="utf-8") as f:
        for i in chosen:
            row = ds[i]
            case = {
                "id": f"gsm8k_test_{i:04d}",
                "inputs": {"question": row["question"]},
                "expected": final_answer(row["answer"]),
                "tags": ["gsm8k"],
            }
            f.write(json.dumps(case, ensure_ascii=False) + "\n")
    (HERE / "case_ids.txt").write_text(
        "\n".join(f"gsm8k_test_{i:04d}" for i in chosen) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(chosen)} cases to {args.out} (seed {args.seed})")


if __name__ == "__main__":
    main()
