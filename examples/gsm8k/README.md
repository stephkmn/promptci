# GSM8K example

Grade-school math word problems from `openai/gsm8k` (test split, 1319 items). The
suite grades the final number only, extracted from a `#### <number>` line.

## Get the data

```bash
pip install "promptci[datasets]"
python examples/gsm8k/download.py --n 200 --seed 0
```

This writes `cases.jsonl` (200 rows, not committed) and `case_ids.txt` (committed,
so the exact subset is reproducible). Five items are inline in `suite.yaml` so the
suite loads and the unit tests pass without the download; they are excluded from
the sample.

## Run

```bash
promptci validate examples/gsm8k/suite.yaml
promptci run examples/gsm8k/suite.yaml --model ollama/qwen2.5:7b --limit 10   # smoke test
promptci run examples/gsm8k/suite.yaml --model ollama/qwen2.5:7b              # all 205
```

## Things to check before reporting a number

Look at 10 failing outputs by hand. Separate "wrong answer" from "right answer,
wrong format" (no `####` line). If the second group is large, that is a finding
about instruction following, not arithmetic, and the report should say so.
