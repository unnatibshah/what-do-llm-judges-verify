# Verifier probe (D33), dev split

D33 verifier probe, dev split: engineering evidence only, not a result.

Cells: k/n (clusters). Right = planted clause named with the reason of its class (D32); clause = named, any reason; wrong = named, never with the right reason; FPR = any finding (D30: invalid counts) on the matched controls of S-both/S-swap/J/A, and on condition C.

## kbench-claude-opus-4-5

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 34/42 (14cl) | - | - | - | 42/42 (14cl) | 8/42 (14cl) | 40/42 (14cl) | 12/42 (14cl) | 38/42 (14cl) | 11/42 (14cl) | 0/126 (14cl) |
| validity-regstatus | 35/42 (14cl) | - | - | - | 42/42 (14cl) | 7/42 (14cl) | 37/42 (14cl) | 11/42 (14cl) | 36/42 (14cl) | 10/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s0 | 29/42 (14cl) | - | - | - | 42/42 (14cl) | 13/42 (14cl) | 37/42 (14cl) | 11/42 (14cl) | 36/42 (14cl) | 10/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s0 | 35/42 (14cl) | - | - | - | 42/42 (14cl) | 7/42 (14cl) | 37/42 (14cl) | 11/42 (14cl) | 36/42 (14cl) | 10/42 (14cl) | 0/126 (14cl) |
| validity-regnorec | 35/42 (14cl) | - | - | - | 42/42 (14cl) | 7/42 (14cl) | 42/42 (14cl) | 10/42 (14cl) | 39/42 (14cl) | 13/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s0 | 30/42 (14cl) | - | - | - | 42/42 (14cl) | 12/42 (14cl) | 42/42 (14cl) | 10/42 (14cl) | 39/42 (14cl) | 11/42 (14cl) | 0/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 4/4 (3cl) | 30/38 (14cl) | 0.5238 |
| validity-regstatus | S-both | 4/4 (3cl) | 31/38 (14cl) | 0.5714 |
| validity-regstatus-drop50-s0 | S-both | 3/4 (3cl) | 26/38 (14cl) | 0.4286 |
| validity-regstatus-spurious10-s0 | S-both | 4/4 (3cl) | 31/38 (14cl) | 0.5714 |
| validity-regnorec | S-both | 4/4 (3cl) | 31/38 (14cl) | 0.5952 |
| validity-regnorec-drop50-s0 | S-both | 3/4 (3cl) | 27/38 (14cl) | 0.4762 |

## Contrasts (right-reason sensitivity, cluster sign-flip; dev has 3 clusters, so p >= 0.25)

| scope | contrast | items | clusters | diff | p | FPR diff | P4 non-inferiority p / TOST p |
|---|---|---|---|---|---|---|---|
| pooled | P2 validity - support | 0 | - | - | None | - |  |
| pooled | P3 meta on - off (support) | 0 | - | - | None | - |  |
| pooled | P4 100-neutral - support | 0 | - | - | None | - |  |
| pooled | P5 reg-real - support | 0 | - | - | None | - |  |
| kbench-claude-opus-4-5 | P2 validity - support | 0 | - | - | None | - |  |
| kbench-claude-opus-4-5 | P3 meta on - off (support) | 0 | - | - | None | - |  |
| kbench-claude-opus-4-5 | P4 100-neutral - support | 0 | - | - | None | - |  |
| kbench-claude-opus-4-5 | P5 reg-real - support | 0 | - | - | None | - |  |

## Wall-clock per block

| model | block | items | calls | seconds | calls/min |
|---|---|---|---|---|---|
| kbench-claude-opus-4-5 | validity__S-both | 84 | 84 | 321.2 | 15.69 |
| kbench-claude-opus-4-5 | validity__C | 42 | 42 | 130.1 | 19.37 |
| kbench-claude-opus-4-5 | validity-regstatus__S-both | 84 | 84 | 278.5 | 18.1 |
| kbench-claude-opus-4-5 | validity-regstatus__C | 42 | 42 | 125.7 | 20.05 |
| kbench-claude-opus-4-5 | validity-regnorec__S-both | 84 | 84 | 231.1 | 21.81 |
| kbench-claude-opus-4-5 | validity-regnorec__C | 42 | 42 | 128.9 | 19.55 |
| kbench-claude-opus-4-5 | validity-regstatus-drop50-s0__S-both | 84 | 84 | 104.7 | 48.14 |
| kbench-claude-opus-4-5 | validity-regstatus-drop50-s0__C | 42 | 42 | 23.0 | 109.57 |
| kbench-claude-opus-4-5 | validity-regnorec-drop50-s0__S-both | 84 | 84 | 102.3 | 49.27 |
| kbench-claude-opus-4-5 | validity-regnorec-drop50-s0__C | 42 | 42 | 20.4 | 123.53 |
| kbench-claude-opus-4-5 | validity-regstatus-spurious10-s0__S-both | 84 | 84 | 0.1 | 50400.0 |
| kbench-claude-opus-4-5 | validity-regstatus-spurious10-s0__C | 42 | 42 | 0.1 | 25200.0 |
