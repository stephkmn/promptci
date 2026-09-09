## Run `709f7dfbc0e6`: json_extract on `ollama/qwen2.5:7b`

| Metric | Value |
|---|---|
| Cases | 72 |
| Errors | 0 |
| Mean score | 0.781 |
| Pass rate | 44.4% |
| Mean latency | 2275 ms |
| p95 latency | 6440 ms |
| Prompt tokens | 12447 |
| Completion tokens | 2838 |
| Total cost | $0.0000 |
| Cache hit rate | 16.7% |

Suite hash `09d758c6b88b7795`, git `472edaa`, started 2026-09-08T21:55:49+00:00, finished 2026-09-08T21:57:25+00:00.

### Lowest-scoring cases (up to 5)

| Case | Score | Output (truncated) | Note |
|---|---|---|---|
| c016 | 0.00 | ```json {   "name": "Self-stirring coffee mug",   "price": null,   "currency": n | schema: in_stock: None is not of type 'boolean' |
| c030 | 0.00 | {   "name": "Prismatic evolutions booster pack",   "price": null,   "currency":  | schema: in_stock: None is not of type 'boolean' |
| c019 | 0.25 | {   "name": "50 in. Blue Dragon mouse pad",   "price": null,   "currency": null, | wrong: currency, name, price |
| c051 | 0.25 | ```json {   "name": "Elephantina's dollhouse playset for kids 3 years and older" | wrong: currency, name, price |
| c002 | 0.50 | ```json {   "name": "Nimbus 2 wireless mouse",   "price": null,   "currency": "E | wrong: name, price |
