# Quality report

This report uses the run of 2026-10-04 with the option `--adjudicate`. We did not do the manual check of 20 matches. No person checked the choices of the model.

## Match status

| Measure | Value |
|---|---|
| Rows in the seed file | 500 |
| Valid seed names | 498 |
| Invalid seed names | 2 |
| `matched` by the rule | 453 |
| `ambiguous` by the rule | 45 |
| `ambiguous` resolved by the model | 44 |
| `ambiguous` resolved by the dominance rule | 0 |
| Final status `matched` | 497 |
| Final status `ambiguous` | 1 |
| Final status `not_found` | 0 |
| Final status `invalid` | 2 |
| Distinct QIDs in the `matched` rows | 490 |
| Rows with `duplicate_of` | 7 |

## What we checked

- The top candidate was correct for 30 of 30 hand-picked names. We checked each result by eye. The names include the special cases of the seed file.
- The 7 rows with `duplicate_of` are the 7 expected pseudonym pairs. No other pair shares a QID.
- The seed file has no exact duplicates and no empty row.
- The model gave valid JSON in 90 of 90 calls.
- With reverse order of the candidates, the model kept the same answer in 44 of 45 rows.

## What we did not check

- The precision of the matches. The manual check of 20 matches is not done.
- The 44 choices of the model. In all 44 rows, the model chose the candidate with the highest score. So the model confirms the rule and adds no new information in this run.
- The works from Open Library.

## Doubtful cases

| Seed name | Match status | Reason | What we did |
|---|---|---|---|
| Anonymous | invalid | The name is not an author. | We keep the row with `is_author = false`. |
| Various Authors | invalid | The name is not an author. | We keep the row with `is_author = false`. |
| Alexandre Dumas | ambiguous | The father and the son have the same score of 98.0. The margin is 0.0. The model answered with the son, then with the father, when we changed the order. The sitelinks ratio is 1.6. | We keep the status `ambiguous`. A person must decide. |
| Vicente Huidobro | matched | The `en` label in Wikidata is "Vicente Hohoneo". The `en` description is "colombian poet". The `es` description is "poeta chileno". | We use the `mul` label. The score is 96.0. The data error is in Wikidata. |
| Lewis Carroll | matched | The margin is 9.4. The second candidate is Lewis Carroll Epstein. | The model chose Q38082. |
| Mario Benedetti | matched | The margin is 1.3. Two humans have the same name. | The model chose the top candidate. A person did not check it. |
| Thomas Hardy | matched | The margin is 2.9. Two humans have the same name. | The model chose the top candidate. A person did not check it. |
| Samuel Johnson | matched | The margin is 2.7. Two humans have the same name. | The model chose the top candidate. A person did not check it. |
| L. M. Montgomery | matched | The second candidate is Bernard Montgomery. The label of the first candidate is "Lucy Maud Montgomery". | The model chose the first candidate. |

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
- Wikidata changes over time. The cache in the repository fixes the data of this run.
