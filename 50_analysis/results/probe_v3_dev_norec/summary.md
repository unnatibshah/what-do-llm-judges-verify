# Verifier probe (D33), dev split

D33 verifier probe, dev split: engineering evidence only, not a result.

Cells: k/n (clusters). Right = planted clause named with the reason of its class (D32); clause = named, any reason; wrong = named, never with the right reason; FPR = any finding (D30: invalid counts) on the matched controls of S-both/S-swap/J/A, and on condition C.

## gemma-4-26b-a4b-it

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| reg-real | 28/28 (2cl) | - | - | - | 28/28 (2cl) | 0/28 (2cl) | 0/28 (2cl) | 0/28 (2cl) | 2/54 (3cl) | 2/54 (3cl) | 0/110 (3cl) |
| validity-regstatus | 27/28 (2cl) | - | - | - | 27/28 (2cl) | 0/28 (2cl) | 14/28 (2cl) | 2/28 (2cl) | 31/54 (3cl) | 3/54 (3cl) | 10/110 (3cl) |
| reg-drop50-s0 | 12/28 (2cl) | - | - | - | 12/28 (2cl) | 0/28 (2cl) | 0/28 (2cl) | 0/28 (2cl) | 2/54 (3cl) | 2/54 (3cl) | 0/110 (3cl) |
| validity-regstatus-drop50-s0 | 22/28 (2cl) | - | - | - | 28/28 (2cl) | 6/28 (2cl) | 14/28 (2cl) | 2/28 (2cl) | 31/54 (3cl) | 3/54 (3cl) | 9/110 (3cl) |
| validity-regnorec | 27/28 (2cl) | - | - | - | 27/28 (2cl) | 0/28 (2cl) | 14/28 (2cl) | 2/28 (2cl) | 28/54 (3cl) | 3/54 (3cl) | 10/110 (3cl) |
| validity-regnorec-drop50-s0 | 21/28 (2cl) | - | - | - | 27/28 (2cl) | 6/28 (2cl) | 14/28 (2cl) | 2/28 (2cl) | 28/54 (3cl) | 3/54 (3cl) | 10/110 (3cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| reg-real | S-both | 15/15 (2cl) | 13/13 (2cl) | 1.0 |
| validity-regstatus | S-both | 15/15 (2cl) | 12/13 (2cl) | 0.8929 |
| reg-drop50-s0 | S-both | 7/15 (2cl) | 5/13 (2cl) | 0.4286 |
| validity-regstatus-drop50-s0 | S-both | 11/15 (2cl) | 11/13 (2cl) | 0.7143 |
| validity-regnorec | S-both | 15/15 (2cl) | 12/13 (2cl) | 0.8929 |
| validity-regnorec-drop50-s0 | S-both | 11/15 (2cl) | 10/13 (2cl) | 0.6786 |

## Contrasts (right-reason sensitivity, cluster sign-flip; dev has 3 clusters, so p >= 0.25)

| scope | contrast | items | clusters | diff | p | FPR diff | P4 non-inferiority p / TOST p |
|---|---|---|---|---|---|---|---|
| pooled | P2 validity - support | 0 | - | - | None | - |  |
| pooled | P3 meta on - off (support) | 0 | - | - | None | - |  |
| pooled | P4 100-neutral - support | 0 | - | - | None | - |  |
| pooled | P5 reg-real - support | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P2 validity - support | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P3 meta on - off (support) | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P4 100-neutral - support | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P5 reg-real - support | 0 | - | - | None | - |  |

## Wall-clock per block

| model | block | items | calls | seconds | calls/min |
|---|---|---|---|---|---|
| gemma-4-26b-a4b-it | reg-real__S-both | 56 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-real__C | 54 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus__S-both | 56 | 56 | 799.5 | 4.2 |
| gemma-4-26b-a4b-it | validity-regstatus__C | 54 | 54 | 894.0 | 3.62 |
| gemma-4-26b-a4b-it | reg-drop50-s0__S-both | 56 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop50-s0__C | 54 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s0__S-both | 56 | 56 | 1065.3 | 3.15 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s0__C | 54 | 54 | 113.4 | 28.57 |
| gemma-4-26b-a4b-it | validity-regnorec__S-both | 56 | 56 | 757.3 | 4.44 |
| gemma-4-26b-a4b-it | validity-regnorec__C | 54 | 54 | 520.0 | 6.23 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s0__S-both | 56 | 56 | 421.6 | 7.97 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s0__C | 54 | 54 | 106.5 | 30.42 |
