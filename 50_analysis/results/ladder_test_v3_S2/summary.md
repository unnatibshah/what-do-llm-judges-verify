# Information ladder

Cells: clause-averaged rate (pooled k/n, number of clauses or rule groups). Catch = right-reason catch (D32); FA = any finding on correct answers (D30); C is grouped by rule group.

## gemini-3.5-flash-lite

| rung | catch | FA matched | FA C | can't confirm (faults) | misnamed | invalid |
|---|---|---|---|---|---|---|
| R0 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 2/2 | 0/12 |
| R2 | 0.42 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 1/4 | 0/18 |
| R4 | 0.67 (4/6, 4 u) | 0.17 (2/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 1/5 | 0/18 |

## gemma-4-26b-a4b-it

| rung | catch | FA matched | FA C | can't confirm (faults) | misnamed | invalid |
|---|---|---|---|---|---|---|
| R0 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 2/2 | 0/12 |
| R1 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/12 |
| R2 | 0.00 (0/6, 4 u) | 0.25 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R3 | 0.25 (1/6, 4 u) | 0.25 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 3/4 | 0/18 |
| R4 | 0.25 (1/6, 4 u) | 0.25 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 2/3 | 0/18 |
| R4' | 0.50 (2/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 2/4 | 0/12 |
| R5 | 0.50 (4/12, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/12, 4 u) | 0/4 | 0/24 |
| R0-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 2/2 | 0/12 |
| R1-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 2/2 | 0/12 |
| R2-cc | 0.00 (0/6, 4 u) | 0.25 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 4/4 | 0/18 |
| R4-drop25 | 0.25 (5/30, 4 u) | 0.25 (15/30, 4 u) | 0.17 (10/30, 4 u) | 0.00 (0/30, 4 u) | 10/15 | 0/90 |
| R4-drop50 | 0.25 (5/30, 4 u) | 0.25 (15/30, 4 u) | 0.17 (10/30, 4 u) | 0.00 (0/30, 4 u) | 10/15 | 0/90 |
| R4-spurious10 | 0.25 (5/30, 4 u) | 0.30 (16/30, 4 u) | 0.27 (12/30, 4 u) | 0.00 (0/30, 4 u) | 10/15 | 0/90 |
| R4n | 0.25 (1/6, 4 u) | 0.50 (4/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 2/3 | 0/18 |
| R4n-drop25 | 0.25 (5/30, 4 u) | 0.50 (20/30, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/30, 4 u) | 10/15 | 0/90 |
| R4n-drop50 | 0.25 (5/30, 4 u) | 0.50 (20/30, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/30, 4 u) | 10/15 | 0/90 |
| R5-drop25 | 0.50 (20/60, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/60, 4 u) | 0/20 | 0/120 |
| R5-drop50 | 0.50 (20/60, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/60, 4 u) | 0/20 | 0/120 |
| R5-spurious10 | 0.50 (20/60, 4 u) | 0.10 (2/30, 4 u) | 0.10 (2/30, 4 u) | 0.00 (0/60, 4 u) | 0/20 | 0/120 |

## llama3.1:8b

| rung | catch | FA matched | FA C | can't confirm (faults) | misnamed | invalid |
|---|---|---|---|---|---|---|
| R0 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/12 |
| R1 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/12 |
| R2 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R3 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4' | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/12 |
| R5 | 0.50 (4/12, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/12, 4 u) | 0/4 | 0/24 |
| R0-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/12 |
| R1-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/12 |
| R2-cc | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4-drop25 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4-drop50 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4-spurious10 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4n-drop25 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4n-drop50 | 0.00 (0/6, 4 u) | 0.58 (3/6, 4 u) | 0.58 (3/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |

## qwen2.5:14b

| rung | catch | FA matched | FA C | can't confirm (faults) | misnamed | invalid |
|---|---|---|---|---|---|---|
| R0 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/12 |
| R1 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/12 |
| R2 | 0.00 (0/6, 4 u) | 0.25 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R3 | 0.00 (0/6, 4 u) | 0.25 (3/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 3/3 | 0/18 |
| R4 | 0.75 (5/6, 4 u) | 0.08 (1/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/5 | 0/18 |
| R4' | 0.58 (3/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/3 | 0/12 |
| R5 | 0.50 (4/12, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/12, 4 u) | 0/4 | 0/24 |
| R0-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/12 |
| R1-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/12 |
| R2-cc | 0.00 (0/6, 4 u) | 0.17 (2/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4-drop25 | 0.70 (22/30, 4 u) | 0.08 (5/30, 4 u) | 0.17 (10/30, 4 u) | 0.00 (0/30, 4 u) | 0/22 | 0/90 |
| R4-drop50 | 0.60 (16/30, 4 u) | 0.08 (5/30, 4 u) | 0.17 (10/30, 4 u) | 0.00 (0/30, 4 u) | 0/16 | 0/90 |
| R4-spurious10 | 0.75 (25/30, 4 u) | 0.18 (7/30, 4 u) | 0.27 (12/30, 4 u) | 0.00 (0/30, 4 u) | 0/25 | 0/90 |
| R4n | 0.75 (5/6, 4 u) | 0.08 (1/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/5 | 0/18 |
| R4n-drop25 | 0.70 (22/30, 4 u) | 0.08 (5/30, 4 u) | 0.17 (10/30, 4 u) | 0.00 (0/30, 4 u) | 0/22 | 0/90 |
| R4n-drop50 | 0.60 (16/30, 4 u) | 0.08 (5/30, 4 u) | 0.17 (10/30, 4 u) | 0.00 (0/30, 4 u) | 0/16 | 0/90 |
| R5-drop25 | 0.50 (20/60, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/60, 4 u) | 0/20 | 0/120 |
| R5-drop50 | 0.50 (20/60, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/30, 4 u) | 0.00 (0/60, 4 u) | 0/20 | 0/120 |
| R5-spurious10 | 0.50 (20/60, 4 u) | 0.10 (2/30, 4 u) | 0.10 (2/30, 4 u) | 0.00 (0/60, 4 u) | 0/20 | 0/120 |

## qwen2.5:7b

| rung | catch | FA matched | FA C | can't confirm (faults) | misnamed | invalid |
|---|---|---|---|---|---|---|
| R0 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/12 |
| R1 | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 1/1 | 0/12 |
| R2 | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 1/1 | 0/18 |
| R3 | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.17 (2/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4 | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4' | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 1/1 | 0/12 |
| R5 | 0.50 (4/12, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/12, 4 u) | 0/4 | 0/24 |
| R0-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/12 |
| R1-cc | 0.00 (0/6, 4 u) | - (0/0, 0 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 1/1 | 0/12 |
| R2-cc | 0.25 (1/6, 4 u) | 0.25 (1/6, 4 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 1/2 | 0/18 |
| R4-drop25 | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4-drop50 | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4-spurious10 | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4n-drop25 | 0.00 (0/6, 4 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |
| R4n-drop50 | 0.00 (0/6, 4 u) | 0.08 (1/6, 4 u) | 0.00 (0/6, 4 u) | 0.00 (0/6, 4 u) | 0/0 | 0/18 |

## Contrasts (per-clause difference in catch; sign-flip over clauses, two-sided)

| contrast | primary | clauses | mean diff | 95% CI | p | p (Holm) |
|---|---|---|---|---|---|---|
| R4-R2 @ gemini-3.5-flash-lite | no | 4 | 0.25 | refused: only 4 clusters (< 10) | 1.0 |  |
| R4-R2 @ gemma-4-26b-a4b-it | no | 4 | 0.25 | refused: only 4 clusters (< 10) | 1.0 |  |
| R4-R2 @ llama3.1:8b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R4-R2 @ qwen2.5:14b | no | 4 | 0.75 | refused: only 4 clusters (< 10) | 0.25 |  |
| R4-R2 @ qwen2.5:7b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R2-R0 @ gemini-3.5-flash-lite | no | 4 | 0.4167 | refused: only 4 clusters (< 10) | 0.5 |  |
| R2-R0 @ gemma-4-26b-a4b-it | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R2-R0 @ llama3.1:8b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R2-R0 @ qwen2.5:14b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R2-R0 @ qwen2.5:7b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R3-R2 @ gemma-4-26b-a4b-it | no | 4 | 0.25 | refused: only 4 clusters (< 10) | 1.0 |  |
| R3-R2 @ llama3.1:8b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R3-R2 @ qwen2.5:14b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R3-R2 @ qwen2.5:7b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R4'-R1 @ gemma-4-26b-a4b-it | no | 4 | 0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| R4'-R1 @ llama3.1:8b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R4'-R1 @ qwen2.5:14b | no | 4 | 0.5833 | refused: only 4 clusters (< 10) | 0.25 |  |
| R4'-R1 @ qwen2.5:7b | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| R5-R4 @ gemma-4-26b-a4b-it | no | 4 | 0.25 | refused: only 4 clusters (< 10) | 1.0 |  |
| R5-R4 @ llama3.1:8b | no | 4 | 0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| R5-R4 @ qwen2.5:14b | no | 4 | -0.25 | refused: only 4 clusters (< 10) | 1.0 |  |
| R5-R4 @ qwen2.5:7b | no | 4 | 0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| (R4-R2) gemma-4-26b-a4b-it - llama3.1:8b | no | 4 | 0.25 | refused: only 4 clusters (< 10) | 1.0 |  |
| (R4-R2) qwen2.5:14b - llama3.1:8b | no | 4 | 0.75 | refused: only 4 clusters (< 10) | 0.25 |  |
| Net-intact @ gemini-3.5-flash-lite | no | 4 | 0.0 | refused: only 4 clusters (< 10) | 1.0 |  |
| Net-intact @ gemma-4-26b-a4b-it | yes | 4 | -0.5 | refused: only 4 clusters (< 10) | 0.5 | 1.0 |
| Net-drop25 @ gemma-4-26b-a4b-it | no | 4 | -0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| Net-drop50 @ gemma-4-26b-a4b-it | yes | 4 | -0.5 | refused: only 4 clusters (< 10) | 0.5 | 1.0 |
| Net-spurious10 @ gemma-4-26b-a4b-it | yes | 4 | -0.45 | refused: only 4 clusters (< 10) | 0.5 | 1.0 |
| Net-intact @ llama3.1:8b | no | 4 | -1.0833 | refused: only 4 clusters (< 10) | 0.25 |  |
| Net-drop25 @ llama3.1:8b | no | 4 | -1.0833 | refused: only 4 clusters (< 10) | 0.25 |  |
| Net-drop50 @ llama3.1:8b | no | 4 | -1.0833 | refused: only 4 clusters (< 10) | 0.25 |  |
| Net-spurious10 @ llama3.1:8b | no | 4 | -0.9833 | refused: only 4 clusters (< 10) | 0.25 |  |
| Net-intact @ qwen2.5:14b | yes | 4 | 0.1667 | refused: only 4 clusters (< 10) | 1.0 | 1.0 |
| Net-drop25 @ qwen2.5:14b | no | 4 | 0.1167 | refused: only 4 clusters (< 10) | 1.0 |  |
| Net-drop50 @ qwen2.5:14b | yes | 4 | 0.0167 | refused: only 4 clusters (< 10) | 1.0 | 1.0 |
| Net-spurious10 @ qwen2.5:14b | yes | 4 | 0.1667 | refused: only 4 clusters (< 10) | 1.0 | 1.0 |
| Net-intact @ qwen2.5:7b | no | 4 | -0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| Net-drop25 @ qwen2.5:7b | no | 4 | -0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| Net-drop50 @ qwen2.5:7b | no | 4 | -0.5 | refused: only 4 clusters (< 10) | 0.5 |  |
| Net-spurious10 @ qwen2.5:7b | no | 4 | -0.4 | refused: only 4 clusters (< 10) | 0.5 |  |

## Discrimination (D48: S-both catch minus matched false alarm, clause-averaged)

| rung, registry, model | clauses | mean | 95% CI |
|---|---|---|---|
| R2 @ gemini-3.5-flash-lite | 4 | 0.25 | only 4 clusters (< 10) |
| R4 intact @ gemini-3.5-flash-lite | 4 | 0.5 | only 4 clusters (< 10) |
| R5 intact @ gemini-3.5-flash-lite | 4 | 0.5 | only 4 clusters (< 10) |
| R5 drop25 @ gemini-3.5-flash-lite | 4 | 0.5 | only 4 clusters (< 10) |
| R5 drop50 @ gemini-3.5-flash-lite | 4 | 0.5 | only 4 clusters (< 10) |
| R5 spurious10 @ gemini-3.5-flash-lite | 4 | 0.4 | only 4 clusters (< 10) |
| R2 @ gemma-4-26b-a4b-it | 4 | -0.25 | only 4 clusters (< 10) |
| R4 intact @ gemma-4-26b-a4b-it | 4 | 0.0 | only 4 clusters (< 10) |
| R5 intact @ gemma-4-26b-a4b-it | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop25 @ gemma-4-26b-a4b-it | 4 | 0.0 | only 4 clusters (< 10) |
| R5 drop25 @ gemma-4-26b-a4b-it | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop50 @ gemma-4-26b-a4b-it | 4 | 0.0 | only 4 clusters (< 10) |
| R5 drop50 @ gemma-4-26b-a4b-it | 4 | 0.5 | only 4 clusters (< 10) |
| R4 spurious10 @ gemma-4-26b-a4b-it | 4 | -0.05 | only 4 clusters (< 10) |
| R5 spurious10 @ gemma-4-26b-a4b-it | 4 | 0.4 | only 4 clusters (< 10) |
| R4n intact @ gemma-4-26b-a4b-it | 4 | -0.25 | only 4 clusters (< 10) |
| R4n drop25 @ gemma-4-26b-a4b-it | 4 | -0.25 | only 4 clusters (< 10) |
| R4n drop50 @ gemma-4-26b-a4b-it | 4 | -0.25 | only 4 clusters (< 10) |
| R2 @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R4 intact @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R5 intact @ llama3.1:8b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop25 @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R5 drop25 @ llama3.1:8b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop50 @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R5 drop50 @ llama3.1:8b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 spurious10 @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R5 spurious10 @ llama3.1:8b | 4 | 0.4 | only 4 clusters (< 10) |
| R4n drop25 @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R4n drop50 @ llama3.1:8b | 4 | -0.5833 | only 4 clusters (< 10) |
| R2 @ qwen2.5:14b | 4 | -0.25 | only 4 clusters (< 10) |
| R4 intact @ qwen2.5:14b | 4 | 0.6667 | only 4 clusters (< 10) |
| R5 intact @ qwen2.5:14b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop25 @ qwen2.5:14b | 4 | 0.6167 | only 4 clusters (< 10) |
| R5 drop25 @ qwen2.5:14b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop50 @ qwen2.5:14b | 4 | 0.5167 | only 4 clusters (< 10) |
| R5 drop50 @ qwen2.5:14b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 spurious10 @ qwen2.5:14b | 4 | 0.5667 | only 4 clusters (< 10) |
| R5 spurious10 @ qwen2.5:14b | 4 | 0.4 | only 4 clusters (< 10) |
| R4n intact @ qwen2.5:14b | 4 | 0.6667 | only 4 clusters (< 10) |
| R4n drop25 @ qwen2.5:14b | 4 | 0.6167 | only 4 clusters (< 10) |
| R4n drop50 @ qwen2.5:14b | 4 | 0.5167 | only 4 clusters (< 10) |
| R2 @ qwen2.5:7b | 4 | 0.0 | only 4 clusters (< 10) |
| R4 intact @ qwen2.5:7b | 4 | 0.0 | only 4 clusters (< 10) |
| R5 intact @ qwen2.5:7b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop25 @ qwen2.5:7b | 4 | 0.0 | only 4 clusters (< 10) |
| R5 drop25 @ qwen2.5:7b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 drop50 @ qwen2.5:7b | 4 | 0.0 | only 4 clusters (< 10) |
| R5 drop50 @ qwen2.5:7b | 4 | 0.5 | only 4 clusters (< 10) |
| R4 spurious10 @ qwen2.5:7b | 4 | 0.0 | only 4 clusters (< 10) |
| R5 spurious10 @ qwen2.5:7b | 4 | 0.4 | only 4 clusters (< 10) |
| R4n drop25 @ qwen2.5:7b | 4 | -0.0833 | only 4 clusters (< 10) |
| R4n drop50 @ qwen2.5:7b | 4 | -0.0833 | only 4 clusters (< 10) |

## Spurious links (E3': controls the spurious registry flags; false alarms R4-spurious10 vs R2)

| model | items | R4 | R2 |
|---|---|---|---|
| gemini-3.5-flash-lite | 0 | 0 | 0 |
| gemma-4-26b-a4b-it | 2 | 1 | 0 |
| llama3.1:8b | 0 | 0 | 0 |
| qwen2.5:14b | 2 | 2 | 0 |
| qwen2.5:7b | 0 | 0 | 0 |
