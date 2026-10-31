# Amendment-link audit table, v1 (D49)

`links.csv` is built by `30_code/scripts/build_link_audit.py` and checked by it (`check`) before writing. No label is
created by the build: every value comes from the registry or from the annotation files.

| Column | Source | Meaning |
|---|---|---|
| `link_id` | edge index in `40_data/registries/registry_real_v2_r3.json` | `L000`… as the seal reads it |
| `old_clause_id`, `new_clause_id` | registry | the clause said to be changed, and the clause that changes it |
| `registry_relation`, `registry_effective_date`, `registry_confidence`, `registry_quote` | registry (AI extractor) | what the non-gold registry asserts |
| `checked_as` | `20_method/annotation/LINKS_KEY_DO_NOT_SHARE.csv` | `test_pair` (used by a test item), `quality_sample` (seeded 20% random sample of the other links), or `not_checked` |
| `a_relation`, `b_relation` | annotator sheets A and B | raw, unedited answers (blank where that annotator did not have the link) |
| `adjudicated_relation`, `adjudicated_effective_date`, `adjudicated_wording`, `decided_by` | `20_method/annotation/adjudication/links_ADJUDICATED.csv` | the human answer after adjudication |
| `outcome` | derived | `confirmed`, `relation_changed`, `not_a_link` (adjudicated NO_CHANGE), `unclear`, `not_checked` |
| `label_provenance` | derived | `human (annotators, adjudicated)` or `AI extractor, provisional` |

What it can and cannot support: the `quality_sample` rows estimate how often a link the registry asserts is wrong.
They do not measure links the registry is missing; nothing in the audit looked for those. `not_checked` rows are
provisional and are not used as gold anywhere.
