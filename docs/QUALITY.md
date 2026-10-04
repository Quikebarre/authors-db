# Quality report

This report uses the run of 2026-10-04 with the option `--adjudicate`. No person has checked the matches yet. The column `correct_human` in `data/output/review_sample.csv` is empty. The column `agent_verdict` holds the verdict of the AI agent. It is not a manual validation.

## Match status

| Measure | Value |
|---|---|
| Rows in the seed file | 500 |
| Valid seed names | 498 |
| Invalid seed names | 2 |
| `matched` by the rule | 453 |
| `ambiguous` by the rule | 45 |
| `ambiguous` resolved by the model | 44 |
| Final status `matched` | 497 |
| Final status `ambiguous` | 1 |
| Final status `not_found` | 0 |
| Final status `invalid` | 2 |
| Distinct QIDs in the `matched` rows | 490 |
| Rows with `duplicate_of` | 7 |

## Independent check with the Open Library link

Each Open Library record can name its Wikidata ID. We compare this ID with our QID. The check does not depend on our score. It covers the 490 distinct QIDs of the `matched` rows.

| Result | QIDs |
|---|---|
| `match`: Open Library names our QID | 450 |
| `mismatch`: Open Library names another QID | 0 |
| `absent`: the Open Library record has no Wikidata ID | 27 |
| `no_ol_id`: Wikidata has no Open Library ID | 13 |

Of the 450 QIDs with a Wikidata ID in Open Library, 450 agree with our match. The lower bound of the 95% Wilson interval is 99.2%. A `match` means that the selected Open Library record names our QID.

We also checked all records, not only the selected ones. The 579 records have 533 `match` and 46 `absent`. No record names another QID. The 13 QIDs with no Open Library ID have no record.

The check cannot find an error that both sources share. It does not cover the 40 QIDs with no link.

## Conflicts between the sources

The conflict flag compares the years of Wikidata and Open Library. The value in `authors` always comes from Wikidata. The flag is empty when a year is absent or is not a plain date.

| Field | Equal | Conflict | Not comparable |
|---|---|---|---|
| `birth_year` | 439 | 10 | 28 |
| `death_year` | 319 | 2 | 156 |

## Manual sample

The file `data/output/review_sample.csv` has 20 rows in two strata. The first stratum has 10 rows that the rule matched. A fixed hash chooses them. The second stratum has the 10 rows that the model resolved with the lowest margin.

| Stratum | Rows | Agent: correct | Agent: plausible | Human verdict |
|---|---|---|---|---|
| Rule | 10 | 10 | 0 | empty |
| Model | 10 | 9 | 1 | empty |

The agent marked 19 of 20 rows as correct. The lower bound of the 95% Wilson interval for 19 of 20 is 76.4%. The sample is small. A person must fill the column `correct_human` before we can quote a precision.

## What we checked

- The top candidate was correct for 30 of 30 hand-picked names. The AI agent checked each result.
- The 7 rows with `duplicate_of` are the 7 expected pseudonym pairs. No other pair shares a QID.
- The seed file has no exact duplicates and no empty row.
- The model gave valid JSON in 45 of 45 first calls. The column `is_valid_output` of `stg_slm_adjudications` shows this.
- The answers for 44 of 45 rows agree in both orders of the candidates. The column `order_consistent` shows this.
- A replay with `--offline --adjudicate` reproduced `author_works`, `field_provenance`, and `review_sample.csv` with no difference. The replay ignores `run_id`. `authors` differed in one row: the confidence of Alexandre Dumas, which we set to empty after the first run.
- Two errors in our code appeared when we read the conflicts. The first error ignored the rank of the Wikidata claims. The second error read "BCE" as a year after the common era. We fixed both, with tests.

## What we did not check

- The precision of the matches. No person checked the 20 rows of the sample.
- The 44 choices of the model. In all 44 rows, the model chose the candidate with the highest score. So the model confirms the rule and adds no new information in this run.
- The 40 QIDs with no Open Library link.

## Doubtful cases

| Seed name | Match status | Reason | What we did |
|---|---|---|---|
| Anonymous | invalid | The name is not an author. | We keep the row with `is_author = false`. |
| Various Authors | invalid | The name is not an author. | We keep the row with `is_author = false`. |
| Alexandre Dumas | ambiguous | The father and the son have the same name and the same score of 98.0. The seed file has no other data. | We keep the status `ambiguous`. See the open decisions in `docs/DECISIONS.md`. |
| Vicente Huidobro | matched | The `en` label in Wikidata is "Vicente Hohoneo". The `en` description is "colombian poet". | We use the `mul` label. The score is 96.0. The error is in Wikidata. |
| Mary Beard | matched | The margin is 0.3. The model chose the classicist born in 1955. The historian Mary Ritter Beard is another possible target. | The agent marked the row as plausible. A person must decide. |
| Francisco de Quevedo | matched | Wikidata marks the year 1584 as preferred. Open Library has 1580. | We keep the Wikidata value. We set the conflict flag. |
| Juan Carlos Onetti | matched | Wikidata has the death year 1994. Open Library has 1948. | We keep the Wikidata value. We set the conflict flag. |
| Ferdowsi | matched | Wikidata has the death year 1020. Open Library has 940. | We keep the Wikidata value. We set the conflict flag. |
| Sappho | matched | Wikidata has the birth year -650. Open Library has 640 BCE. | We keep the Wikidata value. We set the conflict flag. |
| Stendhal | matched | The Open Library record has 0 works. Other authors with 0 works: Lu Xun, Thomas Pynchon, and 12 more. | We keep the row. `author_works` has no rows for these authors. |

## Authors with no Open Library ID

Wikidata has no Open Library ID for 13 authors. We did not search Open Library by name. `authors.open_library_backlink` is `no_ol_id` for them.

- Ahdaf Soueif
- Bapsi Sidhwa
- Bilge Karasu
- Danilo Kiš
- Idea Vilariño
- Kim Young-ha
- Kirmen Uribe
- Lygia Fagundes Telles
- Lídia Jorge
- Nadeem Aslam
- Rosario Castellanos
- Samanta Schweblin
- Shamini Flint

## Pseudonym pairs

All pairs give the same QID. The second row has `duplicate_of`.

| First seed name | Second seed name | QID |
|---|---|---|
| J. K. Rowling | Robert Galbraith | Q34660 |
| Lewis Carroll | Charles Lutwidge Dodgson | Q38082 |
| Mark Twain | Samuel Clemens | Q7245 |
| George Eliot | Mary Ann Evans | Q131333 |
| Karen Blixen | Isak Dinesen | Q182804 |
| Romain Gary | Émile Ajar | Q157322 |
| Dr. Seuss | Theodor Seuss Geisel | Q298685 |

## Limits

- The data covers only authors in Wikidata.
- The writer occupations are a fixed list of 14 QIDs. An author with another occupation can lose 15 points.
- The labels and aliases are in eight languages. A name in another language only can get a lower score.
- The confidence is the score divided by 100. It is not a probability.
- 81 QIDs have more than one Open Library ID. We choose one record. See D16 in `docs/DECISIONS.md`.
- 15 authors have an Open Library record but 0 works in the search. We did not find the cause.
- `first_publish_year` in `author_works` comes from Open Library and can be wrong. For "The Adventures of Tom Sawyer", the value is 1817.
- Wikidata changes over time. The cache in the repository fixes the data of this run.
