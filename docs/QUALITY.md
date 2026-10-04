# Quality report

This report is preliminary. The numbers come from the calibration run on 2026-10-04. The match status is not built yet, and we did not do the manual check of 20 matches.

## Coverage of the calibration run

| Measure | Value |
|---|---|
| Rows in the seed file | 500 |
| Valid seed names | 498 |
| Invalid seed names | 2 |
| Valid seed names with at least one candidate | 498 |
| Top score of 80 or more | 497 |
| Top score below 80 | 1 |
| Top score of 80 or more and margin below 5 | 16 |
| Top score of 80 or more and margin below 10 | 43 |
| Rows that share a QID with another row | 14 |

## What we checked

- The top candidate was correct for 30 of 30 hand-picked names. We checked each result by eye. The names include the special cases of the seed file.
- The 14 rows that share a QID are the 7 expected pseudonym pairs. No other pair shares a QID.
- The seed file has no exact duplicates and no empty row.

## What we did not check yet

- The precision of the matches. The manual check of 20 matches is not done.
- The works from Open Library.
- The result of the language model.

## Doubtful cases

| Seed name | Match status | Reason | What we did |
|---|---|---|---|
| Anonymous | invalid | The name is not an author. | We mark it `not_an_author`. |
| Various Authors | invalid | The name is not an author. | We mark it `not_an_author`. |
| Vicente Huidobro | pending | The top score is 77.1. The top candidate is Vicente Hohoneo, a Colombian poet. | The real author is not in the candidates. The case stays visible. We did not find the cause yet. |
| Inca Garcilaso de la Vega | pending | The margin is 6.4. The second candidate is the poet Garcilaso de la Vega. | The top candidate is correct. We keep the case for the margin test. |
| Mario Benedetti | pending | The margin is 1.3. Two humans have the same name. | The top candidate is probably correct. No rule decides it yet. |
| Samuel Johnson | pending | The margin is 2.7. Two humans have the same name. | No rule decides it yet. |
| Thomas Hardy | pending | The margin is 2.9. Two humans have the same name. | No rule decides it yet. |
| James Baldwin | pending | The margin is 2.3. Two humans have the same name. | No rule decides it yet. |
| Robert Browning | pending | The margin is 2.6. Two humans have the same name. | No rule decides it yet. |
| Alice Walker | pending | The margin is 2.8. Two humans have the same name. | No rule decides it yet. |

## Pseudonym pairs

All pairs give the same QID. We will mark the second row with `duplicate_of`.

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
- The score has no rule for namesakes with the same name and the same evidence.
- The writer occupations are a fixed list of 14 QIDs. An author with another occupation can lose 15 points.
- The calibration run uses the labels and aliases in English and Spanish only.
