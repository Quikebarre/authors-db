# Technical decisions

Each decision has four parts: the decision, the reason, the alternatives that we did not use, and the consequences.

## D1. Entity resolution, not web scraping

**Decision.** We treat the task as entity resolution. We use only structured APIs with stable identifiers.

**Reason.** Each decision must be traceable. An identifier such as a QID lets a reader check the result.

**Alternatives that we did not use.** Automatic reads of the HTML pages of book sites. They break often and has no stable identifiers.

**Consequences.** The data covers only authors in Wikidata. The result is easy to verify.

## D2. Wikidata is the main source

**Decision.** Wikidata gives the candidates and the identity. Open Library will give the works. Wikidata links to Open Library with property P648.

**Reason.** Both sources are public and structured. The link between them is data, not a guess.

**Alternatives that we did not use.** VIAF and ISNI as the main source. They have less data about each author.

**Consequences.** Open Library is not built yet. The fields for the works are empty today.

## D3. Two searches for the candidates

**Decision.** For each seed name we run two searches and join the results. The first is `wbsearchentities`. The second is the full-text search with the filter `haswbstatement:P31=Q5`.

**Reason.** The first search finds aliases. The second finds humans only. In the calibration run, the second search found "Leopoldo Alas Clarín" and "Samuel Clemens".

**Alternatives that we did not use.** One search only. It returned asteroids, family names, and articles in the top 7 results.

**Consequences.** Each seed name needs at least 3 requests. The first run of the full seed file takes more than 5 minutes.

## D4. Only humans, and pseudonym items become humans

**Decision.** A candidate must be a human (P31 is Q5). If a result is a pseudonym item (P31 is Q61002), we replace it with the human. We read the human from property P1535, or from P460 if P1535 is empty.

**Reason.** The search for "Robert Galbraith" returns a pseudonym item that is not a human. The user chose to translate it to the human J. K. Rowling.

**Alternatives that we did not use.** Remove the pseudonym items. This loses the link between the pseudonym and the author.

**Consequences.** All 7 pseudonym pairs in the seed file give the same QID. The pseudonym stays as an alias of the human.

## D5. Score formula

**Decision.** The score has four parts. The name similarity has a weight of 0.65. A writer gets 15 points. A candidate with an Open Library ID gets 15 points. Sitelinks give up to 3 points.

**Reason.** Each part is easy to read. The `reason` text of each score lists the parts. Sitelinks only break ties, so the cap is 3.

**Alternatives that we did not use.** A trained model. It needs labeled data and is hard to explain.

**Consequences.** Two humans with the same name and the same evidence differ by less than 3 points. See the doubtful cases in `docs/QUALITY.md`.

## D6. Name similarity

**Decision.** The similarity is the best value of `fuzz.ratio` between the key of the seed name and each label or alias. For a key of two or more tokens, the token set ratio also counts, with a cap of 90.

**Reason.** The cap keeps "homer" different from "Homer Simpson". The token set ratio still helps with "Leopoldo Alas Clarín".

**Alternatives that we did not use.** The token set ratio with no cap. It gives 100 for a name that contains the key.

**Consequences.** A name with an extra token never gets a perfect similarity.

## D7. Duplicates use the same QID

**Decision.** Two seed names are one author if they give the same QID. We will mark `duplicate_of` and keep all rows.

**Reason.** The identifier is evidence from outside the project. A similar name is not evidence.

**Alternatives that we did not use.** Embeddings of names. A name is a short string with no semantic content. An embedding measures similarity, not identity. It gives false positives for namesakes.

**Consequences.** A pseudonym that Wikidata does not know stays as a separate author.

## D8. A language model is optional

**Decision.** A small local language model can choose between candidates, but only for the `ambiguous` rows. It will use a flag. It is not built yet. No model is a source of data.

**Reason.** The model must not create or fill fields. It can only choose a candidate or answer "none".

**Alternatives that we did not use.** A model for all rows. This costs more and is harder to check.

**Consequences.** If we build it, the output is JSON that Pydantic validates. The status is `resolved_by = slm`, with a lower confidence.

## D9. DuckDB in layers

**Decision.** The database has the layers `raw_`, `stg_`, and final tables. All tables have `run_id`. Each step uses `CREATE OR REPLACE`. The export has only the final tables.

**Reason.** A reader can inspect each step. A step can restart from the layer before it, with no new API call.

**Alternatives that we did not use.** One flat table. It hides the intermediate data.

**Consequences.** The `.duckdb` file is larger than the export.

## D10. HTTP cache, rate limit, and offline mode

**Decision.** The client saves each raw response as a JSON file with the URL, the parameters, and the time. The minimum time between requests is 0.4 seconds. The client reads `Retry-After` after an HTTP 429. The User-Agent has the repository URL and no email address.

**Reason.** A cache makes the run repeatable. The first full run got HTTP 429 at 0.2 seconds with 8 threads.

**Alternatives that we did not use.** No cache. Wikidata data changes, so two runs give different results.

**Consequences.** The cache is part of the evidence. An offline run raises `OfflineCacheMissError` for a request that is not in the cache.

## Open decisions

- The score threshold for `matched`. The calibration run suggests 80.
- The margin threshold. A value of 5 marks 16 seed names as `ambiguous`. We did not check yet how many of the 16 are correct.
- The rule for namesakes with the same name. See `docs/QUALITY.md`.
