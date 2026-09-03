# configs/

Runtime configuration that is not part of any one suite.

- `models.yaml`: the model strings used in the milestone experiments, so the same
  names appear in every report. Edit after checking what fits your machine
  (`ollama list`, and see docs/00_START_HERE.md).
- Token prices live in `src/promptci/prices.yaml` because the package needs them at
  runtime. Override with `PROMPTCI_PRICES=/path/to/prices.yaml` once M2 adds that
  option; until then edit the shipped file.

API keys are never configured here. They come from environment variables
(`OPENAI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`,
`ANTHROPIC_API_KEY`).
