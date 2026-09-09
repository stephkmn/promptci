# M1 json_extract failures

This file is a hand-written classification of failures for the json_extract-60 suite (consists of 72 cases total - 12 pre-written cases, 60 cases written by me).

## ollama/qwen2.5:7b
|Error|No. of cases|
|---|---|
|Wrong value|38|
|Missing field|0|
|Invalid JSON|0|
|Schema violation|2|

## ollama/llama3.2:3b
|Error|No. of cases|
|---|---|
|Wrong value|40|
|Missing field|0|
|Invalid JSON|0|
|Schema violation|5|

No missing field and invalid JSON errors were observed in the both model runs.