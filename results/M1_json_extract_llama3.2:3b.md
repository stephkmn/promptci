## Run `d52818ea685b`: json_extract on `ollama/llama3.2:3b`

| Metric | Value |
|---|---|
| Cases | 72 |
| Errors | 0 |
| Mean score | 0.722 |
| Pass rate | 37.5% |
| Mean latency | 661 ms |
| p95 latency | 938 ms |
| Prompt tokens | 11987 |
| Completion tokens | 2122 |
| Total cost | $0.0000 |
| Cache hit rate | 4.2% |

Suite hash `09d758c6b88b7795`, git `472edaa-dirty`, started 2026-09-08T21:58:41+00:00, finished 2026-09-08T21:59:22+00:00.

### Lowest-scoring cases (up to 5)

| Case | Score | Output (truncated) | Note |
|---|---|---|---|
| c027 | 0.00 | {"name": "Limited-edition running shoes", "price": null, "currency": null, "in_s | schema: in_stock: None is not of type 'boolean' |
| c030 | 0.00 | {"name": "Prismatic evolutions booster pack", "price": null, "currency": null, " | schema: in_stock: None is not of type 'boolean' |
| c045 | 0.00 | {"name": "Nimbus 200", "price": null, "currency": null, "in_stock": null} | schema: in_stock: None is not of type 'boolean' |
| c060 | 0.00 | {"name": "DL Gaming chair", "price": null, "currency": null, "in_stock": null} | schema: in_stock: None is not of type 'boolean' |
| c068 | 0.00 | {"name": "Golden Cow night light", "price": 30, "currency": null, "in_stock": nu | schema: in_stock: None is not of type 'boolean' |

### Wrong number vs. Right number, no `####` counts

|Wrong number|Right number, no `####`|
|---|---|
|9|0|

The 0 here is a false positive that stems from a grader bug that I will be fixing.