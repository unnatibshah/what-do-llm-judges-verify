# Verifier probe (D33), dev split

D33 verifier probe, dev split: engineering evidence only, not a result.

Cells: k/n (clusters). Right = planted clause named with the reason of its class (D32); clause = named, any reason; wrong = named, never with the right reason; FPR = any finding (D30: invalid counts) on the matched controls of S-both/S-swap/J/A, and on condition C.

## gemini-3.5-flash-lite

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 19/42 (14cl) | - | - | - | 35/42 (14cl) | 16/42 (14cl) | 20/42 (14cl) | 0/42 (14cl) | 19/42 (14cl) | 2/42 (14cl) | 0/126 (14cl) |
| validity-metaoff | - | 0/38 (13cl) | - | - | 20/38 (13cl) | 20/38 (13cl) | 2/7 (5cl) | 0/7 (5cl) | 19/42 (14cl) | 3/42 (14cl) | 0/87 (14cl) |
| validity-regstatus | 33/42 (14cl) | - | - | - | 37/42 (14cl) | 4/42 (14cl) | 19/42 (14cl) | 3/42 (14cl) | 18/42 (14cl) | 2/42 (14cl) | 0/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 2/4 (3cl) | 17/38 (14cl) | 0.4524 |
| validity-metaoff | S-swap | 0/4 (3cl) | 0/34 (13cl) | 0.0 |
| validity-regstatus | S-both | 3/4 (3cl) | 30/38 (14cl) | 0.7143 |

## gemma-4-26b-a4b-it

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 9/42 (14cl) | 0/38 (13cl) | - | - | 54/80 (14cl) | 45/80 (14cl) | 21/49 (14cl) | 1/49 (14cl) | 17/42 (14cl) | 1/42 (14cl) | 0/171 (14cl) |
| validity-metaoff | - | 0/38 (13cl) | - | - | 18/38 (13cl) | 18/38 (13cl) | 2/7 (5cl) | 1/7 (5cl) | 16/42 (14cl) | 2/42 (14cl) | 0/87 (14cl) |
| reg-real | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| validity-amendquote | 12/42 (14cl) | - | - | - | 34/42 (14cl) | 22/42 (14cl) | 20/42 (14cl) | 0/42 (14cl) | 17/42 (14cl) | 1/42 (14cl) | 0/126 (14cl) |
| validity-regstatus | 25/42 (14cl) | 22/38 (13cl) | - | - | 64/80 (14cl) | 17/80 (14cl) | 22/49 (14cl) | 3/49 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/171 (14cl) |
| validity-cc | 9/42 (14cl) | 0/38 (13cl) | - | - | 51/80 (14cl) | 42/80 (14cl) | 23/49 (14cl) | 4/49 (14cl) | 17/42 (14cl) | 1/42 (14cl) | 0/171 (14cl) |
| validity-cc-metaoff | - | 0/38 (13cl) | - | - | 19/38 (13cl) | 19/38 (13cl) | 1/7 (5cl) | 1/7 (5cl) | 18/42 (14cl) | 1/42 (14cl) | 1/87 (14cl) |
| reg-drop25-s0 | 26/42 (14cl) | 26/38 (13cl) | - | - | 52/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s1 | 29/42 (14cl) | 29/38 (13cl) | - | - | 58/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s2 | 15/42 (14cl) | 15/38 (13cl) | - | - | 30/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s3 | 27/42 (14cl) | 27/38 (13cl) | - | - | 54/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s4 | 28/42 (14cl) | 28/38 (13cl) | - | - | 56/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s0 | 15/42 (14cl) | 15/38 (13cl) | - | - | 30/80 (14cl) | 0/80 (14cl) | 0/49 (14cl) | 0/49 (14cl) | 0/42 (14cl) | 0/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s1 | 20/42 (14cl) | 20/38 (13cl) | - | - | 40/80 (14cl) | 0/80 (14cl) | 0/49 (14cl) | 0/49 (14cl) | 0/42 (14cl) | 0/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s2 | 15/42 (14cl) | 15/38 (13cl) | - | - | 30/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s3 | 21/42 (14cl) | 21/38 (13cl) | - | - | 42/80 (14cl) | 0/80 (14cl) | 0/49 (14cl) | 0/49 (14cl) | 0/42 (14cl) | 0/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s4 | 17/42 (14cl) | 17/38 (13cl) | - | - | 34/80 (14cl) | 0/80 (14cl) | 3/49 (14cl) | 3/49 (14cl) | 3/42 (14cl) | 3/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s0 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s1 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s2 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 11/49 (14cl) | 11/49 (14cl) | 9/42 (14cl) | 9/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s3 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 9/49 (14cl) | 9/49 (14cl) | 7/42 (14cl) | 7/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s4 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 10/49 (14cl) | 10/49 (14cl) | 8/42 (14cl) | 8/42 (14cl) | 0/171 (14cl) |
| validity-regstatus-drop25-s0 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop25-s1 | 19/42 (14cl) | - | - | - | 32/42 (14cl) | 13/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop25-s2 | 17/42 (14cl) | - | - | - | 32/42 (14cl) | 15/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop25-s3 | 23/42 (14cl) | - | - | - | 32/42 (14cl) | 9/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop25-s4 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s0 | 19/42 (14cl) | - | - | - | 32/42 (14cl) | 13/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s1 | 15/42 (14cl) | - | - | - | 32/42 (14cl) | 17/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s2 | 17/42 (14cl) | - | - | - | 32/42 (14cl) | 15/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s3 | 19/42 (14cl) | - | - | - | 31/42 (14cl) | 12/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s4 | 19/42 (14cl) | - | - | - | 32/42 (14cl) | 13/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-spurious10-s0 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-spurious10-s1 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 2/42 (14cl) | 18/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-spurious10-s2 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 22/42 (14cl) | 3/42 (14cl) | 19/42 (14cl) | 3/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-spurious10-s3 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 3/42 (14cl) | 20/42 (14cl) | 3/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-spurious10-s4 | 25/42 (14cl) | - | - | - | 33/42 (14cl) | 8/42 (14cl) | 21/42 (14cl) | 4/42 (14cl) | 19/42 (14cl) | 4/42 (14cl) | 1/126 (14cl) |
| validity-regnorec | 26/42 (14cl) | - | - | - | 33/42 (14cl) | 7/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s0 | 26/42 (14cl) | - | - | - | 33/42 (14cl) | 7/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s1 | 20/42 (14cl) | - | - | - | 33/42 (14cl) | 13/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s2 | 20/42 (14cl) | - | - | - | 32/42 (14cl) | 12/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s3 | 24/42 (14cl) | - | - | - | 33/42 (14cl) | 9/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s4 | 26/42 (14cl) | - | - | - | 33/42 (14cl) | 7/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s0 | 20/42 (14cl) | - | - | - | 32/42 (14cl) | 12/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 14/42 (14cl) | 1/42 (14cl) | 2/126 (14cl) |
| validity-regnorec-drop50-s1 | 16/42 (14cl) | - | - | - | 32/42 (14cl) | 16/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 14/42 (14cl) | 1/42 (14cl) | 2/126 (14cl) |
| validity-regnorec-drop50-s2 | 20/42 (14cl) | - | - | - | 32/42 (14cl) | 12/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 0/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s3 | 20/42 (14cl) | - | - | - | 32/42 (14cl) | 12/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 14/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |
| validity-regnorec-drop50-s4 | 20/42 (14cl) | - | - | - | 32/42 (14cl) | 12/42 (14cl) | 21/42 (14cl) | 2/42 (14cl) | 15/42 (14cl) | 1/42 (14cl) | 1/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 0/4 (3cl) | 9/38 (14cl) | 0.2143 |
| validity | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.1429 |
| validity-metaoff | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.1429 |
| reg-real | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-real | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| validity-amendquote | S-both | 2/4 (3cl) | 10/38 (14cl) | 0.2857 |
| validity-regstatus | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5476 |
| validity-regstatus | S-swap | 2/4 (3cl) | 20/34 (13cl) | 0.7143 |
| validity-cc | S-both | 0/4 (3cl) | 9/38 (14cl) | 0.1429 |
| validity-cc | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.1429 |
| validity-cc-metaoff | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.1429 |
| reg-drop25-s0 | S-both | 4/4 (3cl) | 22/38 (14cl) | 0.5 |
| reg-drop25-s0 | S-swap | 4/4 (3cl) | 22/34 (13cl) | 0.2857 |
| reg-drop25-s1 | S-both | 4/4 (3cl) | 25/38 (14cl) | 0.5714 |
| reg-drop25-s1 | S-swap | 4/4 (3cl) | 25/34 (13cl) | 0.5714 |
| reg-drop25-s2 | S-both | 4/4 (3cl) | 11/38 (14cl) | 0.2381 |
| reg-drop25-s2 | S-swap | 4/4 (3cl) | 11/34 (13cl) | 0.0 |
| reg-drop25-s3 | S-both | 4/4 (3cl) | 23/38 (14cl) | 0.5238 |
| reg-drop25-s3 | S-swap | 4/4 (3cl) | 23/34 (13cl) | 0.5714 |
| reg-drop25-s4 | S-both | 4/4 (3cl) | 24/38 (14cl) | 0.5476 |
| reg-drop25-s4 | S-swap | 4/4 (3cl) | 24/34 (13cl) | 0.2857 |
| reg-drop50-s0 | S-both | 1/4 (3cl) | 14/38 (14cl) | 0.3571 |
| reg-drop50-s0 | S-swap | 1/4 (3cl) | 14/34 (13cl) | 0.2857 |
| reg-drop50-s1 | S-both | 1/4 (3cl) | 19/38 (14cl) | 0.4762 |
| reg-drop50-s1 | S-swap | 1/4 (3cl) | 19/34 (13cl) | 0.5714 |
| reg-drop50-s2 | S-both | 4/4 (3cl) | 11/38 (14cl) | 0.2381 |
| reg-drop50-s2 | S-swap | 4/4 (3cl) | 11/34 (13cl) | 0.0 |
| reg-drop50-s3 | S-both | 3/4 (3cl) | 18/38 (14cl) | 0.5 |
| reg-drop50-s3 | S-swap | 3/4 (3cl) | 18/34 (13cl) | 0.5714 |
| reg-drop50-s4 | S-both | 4/4 (3cl) | 13/38 (14cl) | 0.3333 |
| reg-drop50-s4 | S-swap | 4/4 (3cl) | 13/34 (13cl) | 0.2857 |
| reg-spurious10-s0 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-spurious10-s0 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s1 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-spurious10-s1 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s2 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.5238 |
| reg-spurious10-s2 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s3 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.5714 |
| reg-spurious10-s3 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s4 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.5476 |
| reg-spurious10-s4 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| validity-regstatus-drop25-s0 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5476 |
| validity-regstatus-drop25-s1 | S-both | 2/4 (3cl) | 17/38 (14cl) | 0.4048 |
| validity-regstatus-drop25-s2 | S-both | 2/4 (3cl) | 15/38 (14cl) | 0.3571 |
| validity-regstatus-drop25-s3 | S-both | 2/4 (3cl) | 21/38 (14cl) | 0.5 |
| validity-regstatus-drop25-s4 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5476 |
| validity-regstatus-drop50-s0 | S-both | 1/4 (3cl) | 18/38 (14cl) | 0.4048 |
| validity-regstatus-drop50-s1 | S-both | 1/4 (3cl) | 14/38 (14cl) | 0.3095 |
| validity-regstatus-drop50-s2 | S-both | 2/4 (3cl) | 15/38 (14cl) | 0.3571 |
| validity-regstatus-drop50-s3 | S-both | 1/4 (3cl) | 18/38 (14cl) | 0.4048 |
| validity-regstatus-drop50-s4 | S-both | 2/4 (3cl) | 17/38 (14cl) | 0.4048 |
| validity-regstatus-spurious10-s0 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5476 |
| validity-regstatus-spurious10-s1 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5476 |
| validity-regstatus-spurious10-s2 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5238 |
| validity-regstatus-spurious10-s3 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5238 |
| validity-regstatus-spurious10-s4 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.5 |
| validity-regnorec | S-both | 2/4 (3cl) | 24/38 (14cl) | 0.5714 |
| validity-regnorec-drop25-s0 | S-both | 2/4 (3cl) | 24/38 (14cl) | 0.5714 |
| validity-regnorec-drop25-s1 | S-both | 2/4 (3cl) | 18/38 (14cl) | 0.4286 |
| validity-regnorec-drop25-s2 | S-both | 2/4 (3cl) | 18/38 (14cl) | 0.4286 |
| validity-regnorec-drop25-s3 | S-both | 2/4 (3cl) | 22/38 (14cl) | 0.5238 |
| validity-regnorec-drop25-s4 | S-both | 2/4 (3cl) | 24/38 (14cl) | 0.5714 |
| validity-regnorec-drop50-s0 | S-both | 1/4 (3cl) | 19/38 (14cl) | 0.4286 |
| validity-regnorec-drop50-s1 | S-both | 1/4 (3cl) | 15/38 (14cl) | 0.3333 |
| validity-regnorec-drop50-s2 | S-both | 2/4 (3cl) | 18/38 (14cl) | 0.4286 |
| validity-regnorec-drop50-s3 | S-both | 1/4 (3cl) | 19/38 (14cl) | 0.4286 |
| validity-regnorec-drop50-s4 | S-both | 2/4 (3cl) | 18/38 (14cl) | 0.4286 |

## llama3.1:8b

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 0/42 (14cl) | 0/38 (13cl) | - | - | 45/80 (14cl) | 45/80 (14cl) | 24/49 (14cl) | 16/49 (14cl) | 19/42 (14cl) | 10/42 (14cl) | 3/171 (14cl) |
| validity-metaoff | - | 0/38 (13cl) | - | - | 23/38 (13cl) | 23/38 (13cl) | 5/7 (5cl) | 2/7 (5cl) | 20/42 (14cl) | 11/42 (14cl) | 1/87 (14cl) |
| reg-real | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| validity-amendquote | 0/42 (14cl) | - | - | - | 24/42 (14cl) | 24/42 (14cl) | 19/42 (14cl) | 13/42 (14cl) | 19/42 (14cl) | 10/42 (14cl) | 1/126 (14cl) |
| validity-regstatus | 3/42 (14cl) | 2/38 (13cl) | - | - | 47/80 (14cl) | 42/80 (14cl) | 24/49 (14cl) | 10/49 (14cl) | 20/42 (14cl) | 12/42 (14cl) | 1/171 (14cl) |
| validity-cc | 0/42 (14cl) | 0/38 (13cl) | - | - | 48/80 (14cl) | 48/80 (14cl) | 25/49 (14cl) | 16/49 (14cl) | 20/42 (14cl) | 12/42 (14cl) | 1/171 (14cl) |
| validity-cc-metaoff | - | 0/38 (13cl) | - | - | 24/38 (13cl) | 24/38 (13cl) | 5/7 (5cl) | 3/7 (5cl) | 20/42 (14cl) | 11/42 (14cl) | 0/87 (14cl) |
| validity-regstatus-drop25-s0 | 0/42 (14cl) | - | - | - | 23/42 (14cl) | 23/42 (14cl) | 19/42 (14cl) | 9/42 (14cl) | 20/42 (14cl) | 12/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-drop50-s0 | 0/42 (14cl) | - | - | - | 23/42 (14cl) | 23/42 (14cl) | 19/42 (14cl) | 9/42 (14cl) | 20/42 (14cl) | 12/42 (14cl) | 1/126 (14cl) |
| validity-regstatus-spurious10-s0 | 3/42 (14cl) | - | - | - | 23/42 (14cl) | 20/42 (14cl) | 19/42 (14cl) | 9/42 (14cl) | 20/42 (14cl) | 12/42 (14cl) | 1/126 (14cl) |
| validity-regnorec-drop25-s0 | 1/42 (14cl) | - | - | - | 23/42 (14cl) | 22/42 (14cl) | 19/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 13/42 (14cl) | 1/126 (14cl) |
| validity-regnorec-drop50-s0 | 1/42 (14cl) | - | - | - | 23/42 (14cl) | 22/42 (14cl) | 19/42 (14cl) | 8/42 (14cl) | 20/42 (14cl) | 13/42 (14cl) | 1/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 0/4 (3cl) | 0/38 (14cl) | -0.3095 |
| validity | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.4286 |
| validity-metaoff | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.2857 |
| reg-real | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-real | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| validity-amendquote | S-both | 0/4 (3cl) | 0/38 (14cl) | -0.3095 |
| validity-regstatus | S-both | 0/4 (3cl) | 3/38 (14cl) | -0.1429 |
| validity-regstatus | S-swap | 1/4 (3cl) | 1/34 (13cl) | 0.1429 |
| validity-cc | S-both | 0/4 (3cl) | 0/38 (14cl) | -0.3333 |
| validity-cc | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.2857 |
| validity-cc-metaoff | S-swap | 0/4 (3cl) | 0/34 (13cl) | -0.4286 |
| validity-regstatus-drop25-s0 | S-both | 0/4 (3cl) | 0/38 (14cl) | -0.2143 |
| validity-regstatus-drop50-s0 | S-both | 0/4 (3cl) | 0/38 (14cl) | -0.2143 |
| validity-regstatus-spurious10-s0 | S-both | 0/4 (3cl) | 3/38 (14cl) | -0.1429 |
| validity-regnorec-drop25-s0 | S-both | 0/4 (3cl) | 1/38 (14cl) | -0.1667 |
| validity-regnorec-drop50-s0 | S-both | 0/4 (3cl) | 1/38 (14cl) | -0.1667 |

## qwen2.5:14b

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 13/42 (14cl) | 2/38 (13cl) | - | - | 41/80 (14cl) | 26/80 (14cl) | 21/49 (14cl) | 12/49 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/171 (14cl) |
| validity-metaoff | - | 2/38 (13cl) | - | - | 14/38 (13cl) | 12/38 (13cl) | 2/7 (5cl) | 2/7 (5cl) | 11/42 (14cl) | 8/42 (14cl) | 0/87 (14cl) |
| reg-real | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| validity-amendquote | 12/42 (14cl) | - | - | - | 25/42 (14cl) | 13/42 (14cl) | 16/42 (14cl) | 10/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regstatus | 32/42 (14cl) | 30/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 10/49 (14cl) | 6/49 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/171 (14cl) |
| validity-cc | 8/42 (14cl) | 2/38 (13cl) | - | - | 34/80 (14cl) | 24/80 (14cl) | 13/49 (14cl) | 9/49 (14cl) | 12/42 (14cl) | 8/42 (14cl) | 0/171 (14cl) |
| validity-cc-metaoff | - | 2/38 (13cl) | - | - | 14/38 (13cl) | 12/38 (13cl) | 2/7 (5cl) | 2/7 (5cl) | 8/42 (14cl) | 5/42 (14cl) | 0/87 (14cl) |
| reg-drop25-s0 | 26/42 (14cl) | 26/38 (13cl) | - | - | 52/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s1 | 29/42 (14cl) | 29/38 (13cl) | - | - | 58/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s2 | 15/42 (14cl) | 15/38 (13cl) | - | - | 30/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s3 | 27/42 (14cl) | 27/38 (13cl) | - | - | 54/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop25-s4 | 28/42 (14cl) | 28/38 (13cl) | - | - | 56/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s0 | 15/42 (14cl) | 15/38 (13cl) | - | - | 30/80 (14cl) | 0/80 (14cl) | 0/49 (14cl) | 0/49 (14cl) | 0/42 (14cl) | 0/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s1 | 20/42 (14cl) | 20/38 (13cl) | - | - | 40/80 (14cl) | 0/80 (14cl) | 0/49 (14cl) | 0/49 (14cl) | 0/42 (14cl) | 0/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s2 | 15/42 (14cl) | 15/38 (13cl) | - | - | 30/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s3 | 21/42 (14cl) | 21/38 (13cl) | - | - | 42/80 (14cl) | 0/80 (14cl) | 0/49 (14cl) | 0/49 (14cl) | 0/42 (14cl) | 0/42 (14cl) | 0/171 (14cl) |
| reg-drop50-s4 | 17/42 (14cl) | 17/38 (13cl) | - | - | 34/80 (14cl) | 0/80 (14cl) | 3/49 (14cl) | 3/49 (14cl) | 3/42 (14cl) | 3/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s0 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s1 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s2 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 11/49 (14cl) | 11/49 (14cl) | 9/42 (14cl) | 9/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s3 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 9/49 (14cl) | 9/49 (14cl) | 7/42 (14cl) | 7/42 (14cl) | 0/171 (14cl) |
| reg-spurious10-s4 | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 10/49 (14cl) | 10/49 (14cl) | 8/42 (14cl) | 8/42 (14cl) | 0/171 (14cl) |
| validity-regstatus-drop25-s0 | 28/42 (14cl) | - | - | - | 31/42 (14cl) | 3/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop25-s1 | 26/42 (14cl) | - | - | - | 29/42 (14cl) | 3/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop25-s2 | 17/42 (14cl) | - | - | - | 29/42 (14cl) | 12/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop25-s3 | 29/42 (14cl) | - | - | - | 29/42 (14cl) | 0/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop25-s4 | 25/42 (14cl) | - | - | - | 28/42 (14cl) | 3/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop50-s0 | 17/42 (14cl) | - | - | - | 20/42 (14cl) | 3/42 (14cl) | 11/42 (14cl) | 7/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop50-s1 | 20/42 (14cl) | - | - | - | 24/42 (14cl) | 4/42 (14cl) | 11/42 (14cl) | 7/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop50-s2 | 17/42 (14cl) | - | - | - | 29/42 (14cl) | 12/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop50-s3 | 19/42 (14cl) | - | - | - | 20/42 (14cl) | 1/42 (14cl) | 11/42 (14cl) | 7/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop50-s4 | 15/42 (14cl) | - | - | - | 23/42 (14cl) | 8/42 (14cl) | 11/42 (14cl) | 7/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s0 | 32/42 (14cl) | - | - | - | 32/42 (14cl) | 0/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s1 | 32/42 (14cl) | - | - | - | 32/42 (14cl) | 0/42 (14cl) | 10/42 (14cl) | 6/42 (14cl) | 11/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s2 | 32/42 (14cl) | - | - | - | 32/42 (14cl) | 0/42 (14cl) | 12/42 (14cl) | 10/42 (14cl) | 13/42 (14cl) | 10/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s3 | 32/42 (14cl) | - | - | - | 32/42 (14cl) | 0/42 (14cl) | 12/42 (14cl) | 8/42 (14cl) | 13/42 (14cl) | 8/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s4 | 32/42 (14cl) | - | - | - | 32/42 (14cl) | 0/42 (14cl) | 11/42 (14cl) | 8/42 (14cl) | 13/42 (14cl) | 9/42 (14cl) | 0/126 (14cl) |
| validity-regnorec | 31/42 (14cl) | - | - | - | 32/42 (14cl) | 1/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s0 | 28/42 (14cl) | - | - | - | 32/42 (14cl) | 4/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s1 | 29/42 (14cl) | - | - | - | 30/42 (14cl) | 1/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s2 | 18/42 (14cl) | - | - | - | 30/42 (14cl) | 12/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s3 | 29/42 (14cl) | - | - | - | 30/42 (14cl) | 1/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s4 | 25/42 (14cl) | - | - | - | 28/42 (14cl) | 3/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s0 | 18/42 (14cl) | - | - | - | 21/42 (14cl) | 3/42 (14cl) | 11/42 (14cl) | 4/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s1 | 23/42 (14cl) | - | - | - | 26/42 (14cl) | 3/42 (14cl) | 11/42 (14cl) | 4/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s2 | 18/42 (14cl) | - | - | - | 30/42 (14cl) | 12/42 (14cl) | 13/42 (14cl) | 5/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s3 | 20/42 (14cl) | - | - | - | 22/42 (14cl) | 2/42 (14cl) | 11/42 (14cl) | 4/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s4 | 16/42 (14cl) | - | - | - | 23/42 (14cl) | 7/42 (14cl) | 12/42 (14cl) | 4/42 (14cl) | 12/42 (14cl) | 7/42 (14cl) | 0/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 1/4 (3cl) | 12/38 (14cl) | 0.0476 |
| validity | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.1429 |
| validity-metaoff | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.2857 |
| reg-real | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-real | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| validity-amendquote | S-both | 0/4 (3cl) | 12/38 (14cl) | 0.0476 |
| validity-regstatus | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.619 |
| validity-regstatus | S-swap | 2/4 (3cl) | 28/34 (13cl) | 1.0 |
| validity-cc | S-both | 0/4 (3cl) | 8/38 (14cl) | 0.0 |
| validity-cc | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.1429 |
| validity-cc-metaoff | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.2857 |
| reg-drop25-s0 | S-both | 4/4 (3cl) | 22/38 (14cl) | 0.5 |
| reg-drop25-s0 | S-swap | 4/4 (3cl) | 22/34 (13cl) | 0.2857 |
| reg-drop25-s1 | S-both | 4/4 (3cl) | 25/38 (14cl) | 0.5714 |
| reg-drop25-s1 | S-swap | 4/4 (3cl) | 25/34 (13cl) | 0.5714 |
| reg-drop25-s2 | S-both | 4/4 (3cl) | 11/38 (14cl) | 0.2381 |
| reg-drop25-s2 | S-swap | 4/4 (3cl) | 11/34 (13cl) | 0.0 |
| reg-drop25-s3 | S-both | 4/4 (3cl) | 23/38 (14cl) | 0.5238 |
| reg-drop25-s3 | S-swap | 4/4 (3cl) | 23/34 (13cl) | 0.5714 |
| reg-drop25-s4 | S-both | 4/4 (3cl) | 24/38 (14cl) | 0.5476 |
| reg-drop25-s4 | S-swap | 4/4 (3cl) | 24/34 (13cl) | 0.2857 |
| reg-drop50-s0 | S-both | 1/4 (3cl) | 14/38 (14cl) | 0.3571 |
| reg-drop50-s0 | S-swap | 1/4 (3cl) | 14/34 (13cl) | 0.2857 |
| reg-drop50-s1 | S-both | 1/4 (3cl) | 19/38 (14cl) | 0.4762 |
| reg-drop50-s1 | S-swap | 1/4 (3cl) | 19/34 (13cl) | 0.5714 |
| reg-drop50-s2 | S-both | 4/4 (3cl) | 11/38 (14cl) | 0.2381 |
| reg-drop50-s2 | S-swap | 4/4 (3cl) | 11/34 (13cl) | 0.0 |
| reg-drop50-s3 | S-both | 3/4 (3cl) | 18/38 (14cl) | 0.5 |
| reg-drop50-s3 | S-swap | 3/4 (3cl) | 18/34 (13cl) | 0.5714 |
| reg-drop50-s4 | S-both | 4/4 (3cl) | 13/38 (14cl) | 0.3333 |
| reg-drop50-s4 | S-swap | 4/4 (3cl) | 13/34 (13cl) | 0.2857 |
| reg-spurious10-s0 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-spurious10-s0 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s1 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-spurious10-s1 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s2 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.5238 |
| reg-spurious10-s2 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s3 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.5714 |
| reg-spurious10-s3 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| reg-spurious10-s4 | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.5476 |
| reg-spurious10-s4 | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| validity-regstatus-drop25-s0 | S-both | 2/4 (3cl) | 26/38 (14cl) | 0.5238 |
| validity-regstatus-drop25-s1 | S-both | 2/4 (3cl) | 24/38 (14cl) | 0.4762 |
| validity-regstatus-drop25-s2 | S-both | 2/4 (3cl) | 15/38 (14cl) | 0.2619 |
| validity-regstatus-drop25-s3 | S-both | 2/4 (3cl) | 27/38 (14cl) | 0.5476 |
| validity-regstatus-drop25-s4 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.4524 |
| validity-regstatus-drop50-s0 | S-both | 1/4 (3cl) | 16/38 (14cl) | 0.2381 |
| validity-regstatus-drop50-s1 | S-both | 1/4 (3cl) | 19/38 (14cl) | 0.3095 |
| validity-regstatus-drop50-s2 | S-both | 2/4 (3cl) | 15/38 (14cl) | 0.2619 |
| validity-regstatus-drop50-s3 | S-both | 1/4 (3cl) | 18/38 (14cl) | 0.2857 |
| validity-regstatus-drop50-s4 | S-both | 2/4 (3cl) | 13/38 (14cl) | 0.1905 |
| validity-regstatus-spurious10-s0 | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.619 |
| validity-regstatus-spurious10-s1 | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.619 |
| validity-regstatus-spurious10-s2 | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.5238 |
| validity-regstatus-spurious10-s3 | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.5714 |
| validity-regstatus-spurious10-s4 | S-both | 2/4 (3cl) | 30/38 (14cl) | 0.5714 |
| validity-regnorec | S-both | 2/4 (3cl) | 29/38 (14cl) | 0.619 |
| validity-regnorec-drop25-s0 | S-both | 2/4 (3cl) | 26/38 (14cl) | 0.5476 |
| validity-regnorec-drop25-s1 | S-both | 2/4 (3cl) | 27/38 (14cl) | 0.5714 |
| validity-regnorec-drop25-s2 | S-both | 2/4 (3cl) | 16/38 (14cl) | 0.3095 |
| validity-regnorec-drop25-s3 | S-both | 2/4 (3cl) | 27/38 (14cl) | 0.5714 |
| validity-regnorec-drop25-s4 | S-both | 2/4 (3cl) | 23/38 (14cl) | 0.4762 |
| validity-regnorec-drop50-s0 | S-both | 1/4 (3cl) | 17/38 (14cl) | 0.3333 |
| validity-regnorec-drop50-s1 | S-both | 1/4 (3cl) | 22/38 (14cl) | 0.4524 |
| validity-regnorec-drop50-s2 | S-both | 2/4 (3cl) | 16/38 (14cl) | 0.3095 |
| validity-regnorec-drop50-s3 | S-both | 1/4 (3cl) | 19/38 (14cl) | 0.381 |
| validity-regnorec-drop50-s4 | S-both | 2/4 (3cl) | 14/38 (14cl) | 0.2857 |

## qwen2.5:7b

| config | right S-both | right S-swap | right J | right A | clause (all) | wrong (all) | FPR controls | FPR-validity controls | FPR C | FPR-validity C | invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|
| validity | 5/42 (14cl) | 1/38 (13cl) | - | - | 21/80 (14cl) | 15/80 (14cl) | 11/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 4/42 (14cl) | 0/171 (14cl) |
| validity-metaoff | - | 1/38 (13cl) | - | - | 10/38 (13cl) | 9/38 (13cl) | 5/7 (5cl) | 1/7 (5cl) | 9/42 (14cl) | 6/42 (14cl) | 0/87 (14cl) |
| reg-real | 31/42 (14cl) | 31/38 (13cl) | - | - | 62/80 (14cl) | 0/80 (14cl) | 7/49 (14cl) | 7/49 (14cl) | 5/42 (14cl) | 5/42 (14cl) | 0/171 (14cl) |
| validity-amendquote | 6/42 (14cl) | - | - | - | 12/42 (14cl) | 6/42 (14cl) | 8/42 (14cl) | 5/42 (14cl) | 8/42 (14cl) | 6/42 (14cl) | 0/126 (14cl) |
| validity-regstatus | 2/42 (14cl) | 2/38 (13cl) | - | - | 9/80 (14cl) | 5/80 (14cl) | 4/49 (14cl) | 3/49 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 0/171 (14cl) |
| validity-cc | 7/42 (14cl) | 2/38 (13cl) | - | - | 22/80 (14cl) | 13/80 (14cl) | 12/49 (14cl) | 9/49 (14cl) | 5/42 (14cl) | 4/42 (14cl) | 0/171 (14cl) |
| validity-cc-metaoff | - | 2/38 (13cl) | - | - | 11/38 (13cl) | 9/38 (13cl) | 5/7 (5cl) | 2/7 (5cl) | 6/42 (14cl) | 6/42 (14cl) | 0/87 (14cl) |
| validity-regstatus-drop25-s0 | 2/42 (14cl) | - | - | - | 3/42 (14cl) | 1/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-drop50-s0 | 2/42 (14cl) | - | - | - | 3/42 (14cl) | 1/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 0/126 (14cl) |
| validity-regstatus-spurious10-s0 | 2/42 (14cl) | - | - | - | 3/42 (14cl) | 1/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 2/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop25-s0 | 3/42 (14cl) | - | - | - | 4/42 (14cl) | 1/42 (14cl) | 3/42 (14cl) | 3/42 (14cl) | 1/42 (14cl) | 1/42 (14cl) | 0/126 (14cl) |
| validity-regnorec-drop50-s0 | 4/42 (14cl) | - | - | - | 6/42 (14cl) | 2/42 (14cl) | 3/42 (14cl) | 3/42 (14cl) | 1/42 (14cl) | 1/42 (14cl) | 0/126 (14cl) |

Right-reason catches split by outcome (outcome-changing / basis-only), and paired discrimination (fault right-reason minus control validity-reason false alarm, mean per pair):

| config | condition | outcome-changing | basis-only | discrimination |
|---|---|---|---|---|
| validity | S-both | 0/4 (3cl) | 5/38 (14cl) | 0.0 |
| validity | S-swap | 0/4 (3cl) | 1/34 (13cl) | -0.2857 |
| validity-metaoff | S-swap | 0/4 (3cl) | 1/34 (13cl) | -0.1429 |
| reg-real | S-both | 4/4 (3cl) | 27/38 (14cl) | 0.619 |
| reg-real | S-swap | 4/4 (3cl) | 27/34 (13cl) | 0.5714 |
| validity-amendquote | S-both | 0/4 (3cl) | 6/38 (14cl) | 0.0238 |
| validity-regstatus | S-both | 0/4 (3cl) | 2/38 (14cl) | 0.0 |
| validity-regstatus | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.1429 |
| validity-cc | S-both | 0/4 (3cl) | 7/38 (14cl) | -0.0238 |
| validity-cc | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.1429 |
| validity-cc-metaoff | S-swap | 0/4 (3cl) | 2/34 (13cl) | -0.2857 |
| validity-regstatus-drop25-s0 | S-both | 0/4 (3cl) | 2/38 (14cl) | 0.0 |
| validity-regstatus-drop50-s0 | S-both | 0/4 (3cl) | 2/38 (14cl) | 0.0 |
| validity-regstatus-spurious10-s0 | S-both | 0/4 (3cl) | 2/38 (14cl) | 0.0 |
| validity-regnorec-drop25-s0 | S-both | 1/4 (3cl) | 2/38 (14cl) | 0.0 |
| validity-regnorec-drop50-s0 | S-both | 0/4 (3cl) | 4/38 (14cl) | 0.0238 |

## Contrasts (right-reason sensitivity, cluster sign-flip; dev has 3 clusters, so p >= 0.25)

| scope | contrast | items | clusters | diff | p | FPR diff | P4 non-inferiority p / TOST p |
|---|---|---|---|---|---|---|---|
| pooled | P2 validity - support | 0 | - | - | None | - |  |
| pooled | P3 meta on - off (support) | 0 | - | - | None | - |  |
| pooled | P4 100-neutral - support | 0 | - | - | None | - |  |
| pooled | P5 reg-real - support | 0 | - | - | None | - |  |
| gemini-3.5-flash-lite | P2 validity - support | 0 | - | - | None | - |  |
| gemini-3.5-flash-lite | P3 meta on - off (support) | 0 | - | - | None | - |  |
| gemini-3.5-flash-lite | P4 100-neutral - support | 0 | - | - | None | - |  |
| gemini-3.5-flash-lite | P5 reg-real - support | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P2 validity - support | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P3 meta on - off (support) | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P4 100-neutral - support | 0 | - | - | None | - |  |
| gemma-4-26b-a4b-it | P5 reg-real - support | 0 | - | - | None | - |  |
| llama3.1:8b | P2 validity - support | 0 | - | - | None | - |  |
| llama3.1:8b | P3 meta on - off (support) | 0 | - | - | None | - |  |
| llama3.1:8b | P4 100-neutral - support | 0 | - | - | None | - |  |
| llama3.1:8b | P5 reg-real - support | 0 | - | - | None | - |  |
| qwen2.5:14b | P2 validity - support | 0 | - | - | None | - |  |
| qwen2.5:14b | P3 meta on - off (support) | 0 | - | - | None | - |  |
| qwen2.5:14b | P4 100-neutral - support | 0 | - | - | None | - |  |
| qwen2.5:14b | P5 reg-real - support | 0 | - | - | None | - |  |
| qwen2.5:7b | P2 validity - support | 0 | - | - | None | - |  |
| qwen2.5:7b | P3 meta on - off (support) | 0 | - | - | None | - |  |
| qwen2.5:7b | P4 100-neutral - support | 0 | - | - | None | - |  |
| qwen2.5:7b | P5 reg-real - support | 0 | - | - | None | - |  |

## Wall-clock per block

| model | block | items | calls | seconds | calls/min |
|---|---|---|---|---|---|
| gemini-3.5-flash-lite | validity-metaoff__C | 42 | 42 | 169.2 | 14.89 |
| gemini-3.5-flash-lite | validity-metaoff__S-swap | 45 | 45 | 184.4 | 14.64 |
| gemini-3.5-flash-lite | validity__S-both | 84 | 84 | 413.9 | 12.18 |
| gemini-3.5-flash-lite | validity__C | 42 | 42 | 183.3 | 13.75 |
| gemini-3.5-flash-lite | validity-regstatus__S-both | 84 | 84 | 352.8 | 14.29 |
| gemini-3.5-flash-lite | validity-regstatus__C | 42 | 42 | 192.8 | 13.07 |
| gemma-4-26b-a4b-it | validity__S-both | 84 | 84 | 1992.7 | 2.53 |
| gemma-4-26b-a4b-it | validity__C | 42 | 42 | 611.3 | 4.12 |
| gemma-4-26b-a4b-it | validity-regstatus__S-both | 84 | 84 | 941.1 | 5.36 |
| gemma-4-26b-a4b-it | validity-regstatus__C | 42 | 42 | 285.8 | 8.82 |
| gemma-4-26b-a4b-it | validity-regnorec__S-both | 84 | 84 | 660.9 | 7.63 |
| gemma-4-26b-a4b-it | validity-regnorec__C | 42 | 42 | 299.1 | 8.43 |
| gemma-4-26b-a4b-it | reg-real__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-real__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-real__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s0__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s0__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s0__S-swap | 45 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop25-s1__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s1__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s1__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s2__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s2__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s2__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s3__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s3__C | 42 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop25-s3__S-swap | 45 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop25-s4__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s4__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop25-s4__S-swap | 45 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop50-s0__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s0__C | 42 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop50-s0__S-swap | 45 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop50-s1__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s1__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s1__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s2__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s2__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s2__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s3__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s3__C | 42 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop50-s3__S-swap | 45 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-drop50-s4__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s4__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-drop50-s4__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s0__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s0__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s0__S-swap | 45 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s1__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s1__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s1__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s2__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s2__C | 42 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s2__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s3__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s3__C | 42 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s3__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s4__S-both | 84 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s4__C | 42 | 0 | 0.0 | None |
| gemma-4-26b-a4b-it | reg-spurious10-s4__S-swap | 45 | 0 | 0.1 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s0__S-both | 84 | 84 | 45.9 | 109.8 |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s0__C | 42 | 42 | 44.1 | 57.14 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s0__S-both | 84 | 84 | 161.0 | 31.3 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s0__C | 42 | 42 | 54.0 | 46.67 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s0__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s0__C | 42 | 42 | 44.1 | 57.14 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s0__S-both | 84 | 84 | 28.7 | 175.61 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s0__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s0__S-both | 84 | 84 | 250.7 | 20.1 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s0__C | 42 | 42 | 22.6 | 111.5 |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s1__S-both | 84 | 84 | 25.4 | 198.43 |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s1__C | 42 | 42 | 46.4 | 54.31 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s1__S-both | 84 | 84 | 9.4 | 536.17 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s1__C | 42 | 42 | 44.5 | 56.63 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s1__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s1__C | 42 | 42 | 44.1 | 57.14 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s1__S-both | 84 | 84 | 21.2 | 237.74 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s1__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s1__S-both | 84 | 84 | 156.7 | 32.16 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s1__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s2__S-both | 84 | 84 | 107.4 | 46.93 |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s2__C | 42 | 42 | 44.6 | 56.5 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s2__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s2__C | 42 | 42 | 413.8 | 6.09 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s2__S-both | 84 | 84 | 31.3 | 161.02 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s2__C | 42 | 42 | 44.7 | 56.38 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s2__S-both | 84 | 84 | 112.7 | 44.72 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s2__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s2__S-both | 84 | 84 | 0.1 | 50400.0 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s2__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s3__S-both | 84 | 84 | 0.1 | 50400.0 |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s3__C | 42 | 42 | 43.9 | 57.4 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s3__S-both | 84 | 84 | 16.8 | 300.0 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s3__C | 42 | 42 | 43.9 | 57.4 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s3__S-both | 84 | 84 | 5.2 | 969.23 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s3__C | 42 | 42 | 51.4 | 49.03 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s3__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s3__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s3__S-both | 84 | 84 | 64.6 | 78.02 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s3__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s4__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop25-s4__C | 42 | 42 | 43.9 | 57.4 |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s4__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regstatus-drop50-s4__C | 42 | 42 | 49.9 | 50.5 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s4__S-both | 84 | 84 | 12.6 | 400.0 |
| gemma-4-26b-a4b-it | validity-regstatus-spurious10-s4__C | 42 | 42 | 54.7 | 46.07 |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s4__S-both | 84 | 84 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop25-s4__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s4__S-both | 84 | 84 | 44.4 | 113.51 |
| gemma-4-26b-a4b-it | validity-regnorec-drop50-s4__C | 42 | 42 | 0.0 | None |
| gemma-4-26b-a4b-it | validity-metaoff__C | 42 | 42 | 211.5 | 11.91 |
| gemma-4-26b-a4b-it | validity-metaoff__S-swap | 45 | 45 | 240.1 | 11.25 |
| gemma-4-26b-a4b-it | validity__S-swap | 45 | 45 | 308.2 | 8.76 |
| gemma-4-26b-a4b-it | validity-regstatus__S-swap | 45 | 45 | 289.5 | 9.33 |
| gemma-4-26b-a4b-it | validity-amendquote__S-both | 84 | 84 | 319.7 | 15.76 |
| gemma-4-26b-a4b-it | validity-amendquote__C | 42 | 42 | 45.4 | 55.51 |
| gemma-4-26b-a4b-it | validity-cc__S-both | 84 | 84 | 531.2 | 9.49 |
| gemma-4-26b-a4b-it | validity-cc__C | 42 | 42 | 239.9 | 10.5 |
| gemma-4-26b-a4b-it | validity-cc__S-swap | 45 | 45 | 243.8 | 11.07 |
| gemma-4-26b-a4b-it | validity-cc-metaoff__C | 42 | 42 | 223.7 | 11.27 |
| gemma-4-26b-a4b-it | validity-cc-metaoff__S-swap | 45 | 45 | 245.6 | 10.99 |
| llama3.1_8b | validity__S-both | 84 | 84 | 999.1 | 5.04 |
| llama3.1_8b | validity__C | 42 | 42 | 369.7 | 6.82 |
| llama3.1_8b | validity-regstatus__S-both | 84 | 84 | 956.9 | 5.27 |
| llama3.1_8b | validity-regstatus__C | 42 | 42 | 342.0 | 7.37 |
| llama3.1_8b | reg-real__S-both | 84 | 0 | 0.1 | None |
| llama3.1_8b | reg-real__C | 42 | 0 | 0.1 | None |
| llama3.1_8b | reg-real__S-swap | 45 | 0 | 0.0 | None |
| llama3.1_8b | validity-metaoff__C | 42 | 42 | 375.4 | 6.71 |
| llama3.1_8b | validity-metaoff__S-swap | 45 | 45 | 573.6 | 4.71 |
| llama3.1_8b | validity__S-swap | 45 | 45 | 460.3 | 5.87 |
| llama3.1_8b | validity-regstatus__S-swap | 45 | 45 | 349.9 | 7.72 |
| llama3.1_8b | validity-amendquote__S-both | 84 | 84 | 553.5 | 9.11 |
| llama3.1_8b | validity-amendquote__C | 42 | 42 | 87.9 | 28.67 |
| llama3.1_8b | validity-cc__S-both | 84 | 84 | 956.1 | 5.27 |
| llama3.1_8b | validity-cc__C | 42 | 42 | 347.8 | 7.25 |
| llama3.1_8b | validity-cc__S-swap | 45 | 45 | 448.0 | 6.03 |
| llama3.1_8b | validity-cc-metaoff__C | 42 | 42 | 359.3 | 7.01 |
| llama3.1_8b | validity-cc-metaoff__S-swap | 45 | 45 | 433.4 | 6.23 |
| llama3.1_8b | validity-regstatus-drop25-s0__S-both | 84 | 84 | 90.8 | 55.51 |
| llama3.1_8b | validity-regstatus-drop25-s0__C | 42 | 42 | 0.1 | 25200.0 |
| llama3.1_8b | validity-regstatus-drop50-s0__S-both | 84 | 84 | 240.7 | 20.94 |
| llama3.1_8b | validity-regstatus-drop50-s0__C | 42 | 42 | 41.4 | 60.87 |
| llama3.1_8b | validity-regstatus-spurious10-s0__S-both | 84 | 84 | 0.2 | 25200.0 |
| llama3.1_8b | validity-regstatus-spurious10-s0__C | 42 | 42 | 0.1 | 25200.0 |
| llama3.1_8b | validity-regnorec-drop25-s0__S-both | 84 | 84 | 732.9 | 6.88 |
| llama3.1_8b | validity-regnorec-drop25-s0__C | 42 | 42 | 132.6 | 19.0 |
| llama3.1_8b | validity-regnorec-drop50-s0__S-both | 84 | 84 | 247.5 | 20.36 |
| llama3.1_8b | validity-regnorec-drop50-s0__C | 42 | 42 | 41.4 | 60.87 |
| qwen2.5_14b | validity__S-both | 84 | 84 | 716.5 | 7.03 |
| qwen2.5_14b | validity__C | 42 | 42 | 220.7 | 11.42 |
| qwen2.5_14b | validity-regstatus__S-both | 84 | 84 | 588.9 | 8.56 |
| qwen2.5_14b | validity-regstatus__C | 42 | 42 | 217.1 | 11.61 |
| qwen2.5_14b | validity-regnorec__S-both | 84 | 84 | 438.9 | 11.48 |
| qwen2.5_14b | validity-regnorec__C | 42 | 42 | 210.6 | 11.97 |
| qwen2.5_14b | reg-real__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-real__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-real__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s0__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop25-s0__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s0__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s1__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop25-s1__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s1__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s2__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop25-s2__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s2__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s3__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop25-s3__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s3__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s4__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop25-s4__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop25-s4__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s0__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop50-s0__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s0__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s1__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop50-s1__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s1__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s2__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop50-s2__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s2__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s3__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop50-s3__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s3__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s4__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-drop50-s4__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-drop50-s4__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s0__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-spurious10-s0__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s0__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s1__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-spurious10-s1__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s1__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s2__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-spurious10-s2__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s2__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s3__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-spurious10-s3__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s3__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s4__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_14b | reg-spurious10-s4__C | 42 | 0 | 0.0 | None |
| qwen2.5_14b | reg-spurious10-s4__S-swap | 45 | 0 | 0.0 | None |
| qwen2.5_14b | validity-regstatus-drop25-s0__S-both | 84 | 84 | 74.7 | 67.47 |
| qwen2.5_14b | validity-regstatus-drop25-s0__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop50-s0__S-both | 84 | 84 | 146.2 | 34.47 |
| qwen2.5_14b | validity-regstatus-drop50-s0__C | 42 | 42 | 16.0 | 157.5 |
| qwen2.5_14b | validity-regstatus-spurious10-s0__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regstatus-spurious10-s0__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop25-s0__S-both | 84 | 84 | 72.1 | 69.9 |
| qwen2.5_14b | validity-regnorec-drop25-s0__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop50-s0__S-both | 84 | 84 | 122.0 | 41.31 |
| qwen2.5_14b | validity-regnorec-drop50-s0__C | 42 | 42 | 16.0 | 157.5 |
| qwen2.5_14b | validity-regstatus-drop25-s1__S-both | 84 | 84 | 58.2 | 86.6 |
| qwen2.5_14b | validity-regstatus-drop25-s1__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop50-s1__S-both | 84 | 84 | 20.4 | 247.06 |
| qwen2.5_14b | validity-regstatus-drop50-s1__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-spurious10-s1__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regstatus-spurious10-s1__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop25-s1__S-both | 84 | 84 | 51.9 | 97.11 |
| qwen2.5_14b | validity-regnorec-drop25-s1__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop50-s1__S-both | 84 | 84 | 16.1 | 313.04 |
| qwen2.5_14b | validity-regnorec-drop50-s1__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop25-s2__S-both | 84 | 84 | 99.0 | 50.91 |
| qwen2.5_14b | validity-regstatus-drop25-s2__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop50-s2__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regstatus-drop50-s2__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-spurious10-s2__S-both | 84 | 84 | 70.5 | 71.49 |
| qwen2.5_14b | validity-regstatus-spurious10-s2__C | 42 | 42 | 26.3 | 95.82 |
| qwen2.5_14b | validity-regnorec-drop25-s2__S-both | 84 | 84 | 89.1 | 56.57 |
| qwen2.5_14b | validity-regnorec-drop25-s2__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop50-s2__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regnorec-drop50-s2__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop25-s3__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regstatus-drop25-s3__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop50-s3__S-both | 84 | 84 | 35.9 | 140.39 |
| qwen2.5_14b | validity-regstatus-drop50-s3__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-spurious10-s3__S-both | 84 | 84 | 16.2 | 311.11 |
| qwen2.5_14b | validity-regstatus-spurious10-s3__C | 42 | 42 | 13.2 | 190.91 |
| qwen2.5_14b | validity-regnorec-drop25-s3__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regnorec-drop25-s3__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop50-s3__S-both | 84 | 84 | 39.2 | 128.57 |
| qwen2.5_14b | validity-regnorec-drop50-s3__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop25-s4__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regstatus-drop25-s4__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-drop50-s4__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regstatus-drop50-s4__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regstatus-spurious10-s4__S-both | 84 | 84 | 23.9 | 210.88 |
| qwen2.5_14b | validity-regstatus-spurious10-s4__C | 42 | 42 | 19.6 | 128.57 |
| qwen2.5_14b | validity-regnorec-drop25-s4__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regnorec-drop25-s4__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-regnorec-drop50-s4__S-both | 84 | 84 | 0.1 | 50400.0 |
| qwen2.5_14b | validity-regnorec-drop50-s4__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_14b | validity-metaoff__C | 42 | 42 | 205.5 | 12.26 |
| qwen2.5_14b | validity-metaoff__S-swap | 45 | 45 | 255.4 | 10.57 |
| qwen2.5_14b | validity__S-swap | 45 | 45 | 276.0 | 9.78 |
| qwen2.5_14b | validity-regstatus__S-swap | 45 | 45 | 308.2 | 8.76 |
| qwen2.5_14b | validity-amendquote__S-both | 84 | 84 | 383.3 | 13.15 |
| qwen2.5_14b | validity-amendquote__C | 42 | 42 | 38.9 | 64.78 |
| qwen2.5_14b | validity-cc__S-both | 84 | 84 | 556.0 | 9.06 |
| qwen2.5_14b | validity-cc__C | 42 | 42 | 221.6 | 11.37 |
| qwen2.5_14b | validity-cc__S-swap | 45 | 45 | 262.8 | 10.27 |
| qwen2.5_14b | validity-cc-metaoff__C | 42 | 42 | 193.1 | 13.05 |
| qwen2.5_14b | validity-cc-metaoff__S-swap | 45 | 45 | 264.4 | 10.21 |
| qwen2.5_7b | validity__S-both | 84 | 84 | 676.8 | 7.45 |
| qwen2.5_7b | validity__C | 42 | 42 | 167.0 | 15.09 |
| qwen2.5_7b | validity-regstatus__S-both | 84 | 84 | 391.6 | 12.87 |
| qwen2.5_7b | validity-regstatus__C | 42 | 42 | 182.2 | 13.83 |
| qwen2.5_7b | reg-real__S-both | 84 | 0 | 0.1 | None |
| qwen2.5_7b | reg-real__C | 42 | 0 | 0.1 | None |
| qwen2.5_7b | reg-real__S-swap | 45 | 0 | 0.1 | None |
| qwen2.5_7b | validity-metaoff__C | 42 | 42 | 270.3 | 9.32 |
| qwen2.5_7b | validity-metaoff__S-swap | 45 | 45 | 318.4 | 8.48 |
| qwen2.5_7b | validity__S-swap | 45 | 45 | 313.7 | 8.61 |
| qwen2.5_7b | validity-regstatus__S-swap | 45 | 45 | 181.6 | 14.87 |
| qwen2.5_7b | validity-amendquote__S-both | 84 | 84 | 338.7 | 14.88 |
| qwen2.5_7b | validity-amendquote__C | 42 | 42 | 65.7 | 38.36 |
| qwen2.5_7b | validity-cc__S-both | 84 | 84 | 543.3 | 9.28 |
| qwen2.5_7b | validity-cc__C | 42 | 42 | 172.8 | 14.58 |
| qwen2.5_7b | validity-cc__S-swap | 45 | 45 | 202.9 | 13.31 |
| qwen2.5_7b | validity-cc-metaoff__C | 42 | 42 | 263.2 | 9.57 |
| qwen2.5_7b | validity-cc-metaoff__S-swap | 45 | 45 | 323.6 | 8.34 |
| qwen2.5_7b | validity-regstatus-drop25-s0__S-both | 84 | 84 | 45.7 | 110.28 |
| qwen2.5_7b | validity-regstatus-drop25-s0__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_7b | validity-regstatus-drop50-s0__S-both | 84 | 84 | 149.5 | 33.71 |
| qwen2.5_7b | validity-regstatus-drop50-s0__C | 42 | 42 | 22.1 | 114.03 |
| qwen2.5_7b | validity-regstatus-spurious10-s0__S-both | 84 | 84 | 0.2 | 25200.0 |
| qwen2.5_7b | validity-regstatus-spurious10-s0__C | 42 | 42 | 0.1 | 25200.0 |
| qwen2.5_7b | validity-regnorec-drop25-s0__S-both | 84 | 84 | 475.6 | 10.6 |
| qwen2.5_7b | validity-regnorec-drop25-s0__C | 42 | 42 | 163.9 | 15.38 |
| qwen2.5_7b | validity-regnorec-drop50-s0__S-both | 84 | 84 | 97.6 | 51.64 |
| qwen2.5_7b | validity-regnorec-drop50-s0__C | 42 | 42 | 21.7 | 116.13 |
