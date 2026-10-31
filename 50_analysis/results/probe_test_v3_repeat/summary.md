# Verifier probe (D33), dev split

D33 verifier probe, dev split: engineering evidence only, not a result.

Cells: k/n (clusters). Right = planted clause named with the reason of its class (D32); clause = named, any reason; wrong = named, never with the right reason; FPR = any finding (D30: invalid counts) on the matched controls of S-both/S-swap/J/A, and on condition C.

## qwen2.5:14b

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 13/42 (14cl) | - | - | - | 26/42 (14cl) | 13/42 (14cl) | 18/42 (14cl) | 11/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regstatus | 32/42 (14cl) | - | - | - | 32/42 (14cl) | 0/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regnorec | 31/42 (14cl) | - | - | - | 32/42 (14cl) | 1/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 1/4 (3cl) | 12/38 (14cl) | 0.0476 |
| validity-regstatus | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.619 |
| validity-regnorec | S-both | 2/4 (3cl) | 29/38 (14cl) | 0.619 |

## Contrasts (right-reason sensitivity, cluster sign-flip; dev has 3 clusters, so p >= 0.25)

| scope | contrast | items | clusters | diff | p | FPR diff | P4 non-inferiority p / TOST p |
|---|---|---|---|---|---|---|---|
| pooled | P2 validity - support | 0 | - | - | None | - |  |
| pooled | P3 meta on - off (support) | 0 | - | - | None | - |  |
| pooled | P4 100-neutral - support | 0 | - | - | None | - |  |
| pooled | P5 reg-real - support | 0 | - | - | None | - |  |
| qwen2.5:14b | P2 validity - support | 0 | - | - | None | - |  |
| qwen2.5:14b | P3 meta on - off (support) | 0 | - | - | None | - |  |
| qwen2.5:14b | P4 100-neutral - support | 0 | - | - | None | - |  |
| qwen2.5:14b | P5 reg-real - support | 0 | - | - | None | - |  |

## Wall-clock per block

| model | block | items | calls | seconds | calls/min |
|---|---|---|---|---|---|
| qwen2.5_14b | validity__S-both | 84 | 84 | 634.6 | 7.94 |
| qwen2.5_14b | validity__C | 42 | 42 | 220.6 | 11.42 |
| qwen2.5_14b | validity-regstatus__S-both | 84 | 84 | 588.8 | 8.56 |
| qwen2.5_14b | validity-regstatus__C | 42 | 42 | 217.2 | 11.6 |
| qwen2.5_14b | validity-regnorec__S-both | 84 | 84 | 438.6 | 11.49 |
| qwen2.5_14b | validity-regnorec__C | 42 | 42 | 210.4 | 11.98 |
