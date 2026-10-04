# Technical decisions

Each decision has four parts: the decision, the reason, the alternatives that we did not use, and the consequences.

## D1. Entity resolution, not web scraping

**Decision.** We treat the task as entity resolution. We use only structured APIs with stable identifiers.

**Reason.** Each decision must be traceable. An identifier such as a QID lets a reader check the result.

**Alternatives that we did not use.** Automatic reads of the HTML pages of book sites. They break often and have no stable identifiers.

**Consequences.** The data covers only authors in Wikidata. The result is easy to verify.

## D2. Wikidata is the main source

**Decision.** Wikidata gives the candidates and the identity. Open Library will give the works. Wikidata links to Open Library with property P648.

**Reason.** Both sources are public and structured. The link between them is data, not a guess.

**Alternatives that we did not use.** VIAF and ISNI as the main source. They have less data about each author.

**Consequences.** Open Library gives the work count and the main works. See D16.

## D3. Two searches for the candidates

**Decision.** For each seed name we run two searches and join the results. The first is `wbsearchentities`. The second is the full-text search with the filter `haswbstatement:P31=Q5`.

**Reason.** The first search finds aliases. The second finds humans only. In the calibration run, the second search found "Leopoldo Alas Clarín" and "Samuel Clemens".

**Alternatives that we did not use.** One search only. It returned asteroids, family names, and articles in the top 7 results.

**Consequences.** Each seed name needs at least 3 requests. The first full run makes 1,534 requests.

## D4. Only humans, and pseudonym items become humans

**Decision.** A candidate must be a human (P31 is Q5). If a result is a pseudonym item (P31 is Q61002), we replace it with the human. We read the human from property P1535, or from P460 if P1535 is empty.

**Reason.** The search for "Robert Galbraith" returns a pseudonym item that is not a human. The user chose to translate it to the human J. K. Rowling.

**Alternatives that we did not use.** Remove the pseudonym items. This loses the link between the pseudonym and the author.

**Consequences.** All 7 pseudonym pairs in the seed file give the same QID. The pseudonym stays as an alias of the human.

## D5. Labels in eight languages, and the `mul` label first

**Decision.** We request the labels in `en`, `es`, `fr`, `de`, `it`, `pt`, `ca`, and `mul`. The canonical name is the `mul` label. If no `mul` label exists, it is the `en` label.

**Reason.** The `en` label of Q117018 is "Vicente Hohoneo". This is an error in Wikidata. The correct name is in the `mul` and `fr` labels. With two languages, the score of Vicente Huidobro was 77.1. With eight languages, it is 96.0.

**Alternatives that we did not use.** All languages. The responses are much larger.

**Consequences.** An author whose name is in another language only can get a lower score.

## D6. Score formula

**Decision.** The score has four parts. The name similarity has a weight of 0.65. A writer gets 15 points. A candidate with an Open Library ID gets 15 points. Sitelinks give up to 3 points.

**Reason.** Each part is easy to read. The `reason` text of each score lists the parts. Sitelinks only break ties, so the cap is 3.

**Alternatives that we did not use.** A trained model. It needs labeled data and is hard to explain.

**Consequences.** Two humans with the same name and the same evidence differ by less than 3 points.

## D7. Name similarity

**Decision.** The similarity is the best value of `fuzz.ratio` between the key of the seed name and each label or alias. For a key of two or more tokens, the token set ratio also counts, with a cap of 90.

**Reason.** The cap keeps "homer" different from "Homer Simpson". The token set ratio still helps with "Leopoldo Alas Clarín".

**Alternatives that we did not use.** The token set ratio with no cap. It gives 100 for a name that contains the key.

**Consequences.** A name with an extra token never gets a perfect similarity.

## D8. Match status and thresholds

**Decision.** The rule gives a match status from two thresholds, which are in `src/authors_db/config.py`. If the top score is below 80, the status is `not_found`. If the margin is below 10, the status is `ambiguous`. Else the status is `matched`.

**Reason.** In the calibration run, 497 of 498 valid seed names had a top score of 80 or more. A margin below 10 marked 45 seed names. Most of them have a namesake or a relative as the second candidate. A false match is worse than a visible doubt.

**Alternatives that we did not use.** A margin below 5. It marks 17 seed names. The other 28 would pass with no check by the model.

**Consequences.** The rule marks 45 rows as `ambiguous`. The model and the dominance rule resolve 44 of them.

## D9. A local model resolves the `ambiguous` rows

**Decision.** With the option `--adjudicate`, a local model chooses between the candidates of each `ambiguous` row, or answers "none". The model is `qwen2.5:7b-instruct-q4_K_M` in Ollama.

The setup is fixed for each run:

- The digest of the model is pinned in `config.py`.
- The temperature is 0 and the seed is 0.
- The prompt has a version.
- Pydantic validates the JSON answer.
- The cache stores each answer.

**Reason.** The model never creates or fills a field. It only chooses a candidate. A row that the model resolves has `resolved_by = slm` and a confidence factor of 0.8.

**Alternatives that we did not use.** A model for all rows. This costs more and is harder to check. A model as a source of data. We never do this.

**Consequences.** The model chose the candidate with the highest score in all 44 resolved rows. Its value in this run is the check of the rule, and the detection of one unstable row (D10).

## D10. The model must agree in two orders

**Decision.** We ask the model twice. The second time, the candidates are in reverse order. We accept a choice only if both answers give the same candidate.

**Reason.** In the first test, the model answered "A" in 45 of 45 rows. With reverse order, 44 of 45 answers kept the same candidate. For "Alexandre Dumas", the first answer was the son and the second answer was the father. The answer depended on the order, so we do not trust it.

**Alternatives that we did not use.** One question per row. It accepts an answer that depends on the position.

**Consequences.** The cost doubles: 90 calls for 45 rows. One row, "Alexandre Dumas", has no choice from the model.

## D11. Dominance rule

**Decision.** The rule applies only to a row that the model could not resolve. We sort the two best candidates by name similarity, then by sitelinks. The first candidate wins if its sitelinks are at least 3 times the sitelinks of the second candidate. The second candidate must not have a higher name similarity.

**Reason.** A famous candidate is more likely the target. The condition on the name similarity prevents a wrong result. For "Nguyễn Du", Ho Chi Minh has 153 sitelinks and Nguyễn Du has 37. The name similarity of Ho Chi Minh is lower.

**Alternatives that we did not use.** A ratio on the sitelinks alone. It chooses Ho Chi Minh for "Nguyễn Du".

**Consequences.** "Alexandre Dumas" has a ratio of 1.6 (174 and 107). The rule does not resolve it. The status stays `ambiguous`.

## D12. Duplicates use the same QID

**Decision.** Two seed names are one author if they give the same QID. We write `duplicate_of` in the later row and keep all rows.

**Reason.** The identifier is evidence from outside the project. A similar name is not evidence.

**Alternatives that we did not use.** Embeddings of names. A name is a short string with no semantic content. An embedding measures similarity, not identity. It gives false positives for namesakes.

**Consequences.** A pseudonym that Wikidata does not know stays as a separate author. The run marks 7 duplicates.

## D13. Rows that are not authors stay in the table

**Decision.** `Anonymous` and `Various Authors` stay in `authors`. They have `is_author = false`, `invalid_reason = not_an_author`, and `match_status = invalid`.

**Reason.** The user wants one row for each seed name. The row must say that the name is not an author.

**Alternatives that we did not use.** Remove the rows. The count of the output would differ from the input.

**Consequences.** A user of the table must filter on `is_author`.

## D14. DuckDB in layers

**Decision.** The database has the layers `raw_`, `stg_`, and final tables. All tables have `run_id`. Each step uses `CREATE OR REPLACE`. The export has only the final tables.

**Reason.** A reader can inspect each step. A step can restart from the layer before it, with no new API call.

**Alternatives that we did not use.** One flat table. It hides the intermediate data.

**Consequences.** The `.duckdb` file is 179 MB, so it is not in git. The export is in git.

## D15. HTTP cache, rate limit, and offline mode

**Decision.** The client saves each raw response as a compressed JSON file with the URL, the parameters, and the time. The minimum time between requests is 0.4 seconds. The client reads `Retry-After` after an HTTP 429. The User-Agent has the repository URL and no email address.

**Reason.** A cache makes the run repeatable. The first full run got HTTP 429 at 0.2 seconds with 8 threads. Compression reduced the cache from 271 MB to 3.7 MB.

**Alternatives that we did not use.** No cache. Wikidata data changes, so two runs give different results.

**Consequences.** The cache is part of the evidence and is in git. An offline run raises `OfflineCacheMissError` for a request that is not in the cache.

## D16. Open Library: two requests for each author

**Decision.** For each Open Library ID, we read the author record (`/authors/<id>.json`). We also read the search `search.json?author_key=<id>&sort=editions&limit=3`. The first request gives the name, the dates, and the Wikidata ID. The second request gives the number of works and the 3 works with the most editions.

**Reason.** Two requests keep the work small. The sort by editions gives the main works. In a check, "J. K. Rowling" returned the Harry Potter books first.

**Alternatives that we did not use.** The list `/authors/<id>/works.json`. It has no order by popularity.

**Consequences.** Some Wikidata items have two Open Library IDs. We prefer the record that links back to the QID. Then we prefer the record with more works. For "Gabriel García Márquez", the first ID has 0 works and the second ID has the works.

We do not search Open Library by name. This search would be a second problem of entity resolution. A QID with no Open Library ID gets the status `no_ol_id`.

## D17. The Open Library link back to Wikidata is a check

**Decision.** Each Open Library record can contain a Wikidata ID. We compare this ID with our QID. The result is `match`, `mismatch`, `absent`, `ol_not_found`, or `no_ol_id`. The result is in `authors.open_library_backlink`.

**Reason.** The Open Library data is independent of our score. A `match` is evidence from a second source. A `mismatch` shows a possible false match.

**Alternatives that we did not use.** No check. We would have no measure of precision, except a small manual sample.

**Consequences.** The check covers only authors that have an Open Library ID. It cannot find an error that both sources share.

## D18. Provenance and the conflict rule

**Decision.** The table `field_provenance` has one row for each QID, field, and source. It has the value, the retrieval time, and a `conflict` flag. The conflict rule compares years only. The flag is NULL, and the note is `not_comparable`, if one year is absent or the text is not a plain date.

**Reason.** A text such as "427 BC" or "c. 1207" is not comparable with a Wikidata year. A conflict flag in these cases would be a false alarm. The retrieval time moves from the cache record to the `stg_` tables, and from there to this table.

**Alternatives that we did not use.** Compare the full date text. The formats differ between the sources.

**Consequences.** We record conflicts and do not resolve them. The value in `authors` always comes from Wikidata.

## D19. Dates, nationality, and language

**Decision.** `authors` has `birth_year` and `death_year` as integers. The columns `birth_date` and `death_date` have a value only when Wikidata has day precision. The nationality comes from property P27 and the languages from property P1412. We read their labels from Wikidata in `en` and `mul`.

**Reason.** An old version cut the date text and gave values such as `-0900-00-0` for Homer. A year with month precision gave `YYYY-00-00`, which is not a valid date.

**Alternatives that we did not use.** A date column with the Wikidata text. It contains invalid dates.

**Consequences.** The nationality is the value in Wikidata. For "Miguel de Cervantes", it is "Corona de Castilla", not "Spain".

## Open decisions

- **Alexandre Dumas.** The father and the son are both authors with the same name. The seed file has no other data to separate them. The correct result is one entry for the father and one entry for the son. We did not build this. Today the row has the status `ambiguous`.
- **The score for namesakes.** The score has no rule for two humans with the same name and the same evidence. The model resolves these rows today.
- **Authors with no Open Library ID.** We do not search Open Library by name. A search that we accept only when the Wikidata link equals our QID is a safe option.
