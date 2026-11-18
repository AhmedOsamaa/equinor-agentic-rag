# Question-generation prompt (for an external model, one call per document)

How to use: attach ONE PDF per call, fill in the `{{...}}` placeholders (doc_id, title,
counts from the table at the bottom), paste everything from "BEGIN PROMPT" to "END PROMPT".
For the cross-document call use the variant at the bottom. Save the output as
`eval/candidates/<doc_id>.jsonl`. Nothing here goes into the eval until
`verify_candidates.py` and your own review have passed it.

---- BEGIN PROMPT ----

You are helping build an evaluation set for a retrieval-augmented question answering
system. The system answers questions from a fixed set of six public documents. Your job
is to write realistic questions that a person could ask about the ATTACHED document, each
with the evidence that answers it. A human will review every item, and a script will check
every quote against the document text, so accuracy matters more than volume.

## Your document

- doc_id: {{DOC_ID}}
- title: {{TITLE}}

## What a good question looks like

- Written the way a user would ask it, in their own words. Do NOT copy the document's
  sentence structure or reuse its distinctive phrases; paraphrase. A question that can be
  answered by matching its exact words in the document does not test the system.
- Understandable on its own. Never write "according to the text", "in this document",
  "in the table above" or "on page 12". Name the entity, year or regulation instead
  (for example "Equinor's 2025 annual report", "the Activities Regulations").
- Has one clear answer that is stated in the document (except holistic, see below). No
  opinions, no questions needing outside knowledge.
- Questions in one batch must differ: different pages, different topics. Spread them
  across the whole document, not just the first chapters.

## Fields: `type`, `format`, `behaviour`

Every question gets all three.

`type` (what reasoning the answer needs):

| type | meaning | example shape |
| --- | --- | --- |
| `direct_fact` | One stated fact, name or defined value, no calculation. | "Who must ...?" "What is the definition of ...?" |
| `numerical` | The answer is a number, or needs one simple calculation (a sum, difference, ratio or percentage change) from stated numbers. | "By how much did X increase?" "What is the limit for ...?" |
| `temporal` | About a date, period, deadline, sequence, or change over time. | "From when does ... apply?" "How did X change from 2024 to 2025?" |
| `comparative` | Compares two or more entities, years, technologies, categories or requirements. | "Which of A and B is higher/larger?" "How do the requirements for X differ from Y?" |
| `spanning` | Needs information from two or more separate places (different pages or sections). | A definition plus a requirement; a figure plus its explanation. |
| `relationship` | Asks how two things are connected: cause and effect, dependency, who is responsible for what, which requirement applies to which party. | "How does X affect Y?" "Which section governs ...?" |
| `holistic` | Needs an overview of a whole section or theme, not one fact. | "What are the main elements of ...?" |

`format` (where the evidence lives):
- `text`: running text.
- `table`: a value in a table, or a figure's data labels. Only use if the text of the table is selectable in the PDF.

`behaviour` (what a good system should do):

| behaviour | meaning |
| --- | --- |
| `answerable` | The answer is in the document. |
| `unanswerable_out` | Plausible for this kind of document but outside it (another company, another year, another country). |
| `unanswerable_near` | On topic and looks answerable, but the specific detail asked for is NOT stated in the document. A real near-miss, not an absurd one. |
| `ambiguous` | Too vague as asked (missing year, entity or section); a good system should ask a clarifying question. |

For `unanswerable_*` and `ambiguous`, still give the `type` it would have had if it were
answerable and well specified, and `format: "text"` unless it concerns a table.

## Evidence rules (checked by a script)

For every `answerable` question give 1 to 3 evidence items (holistic: 2 to 5). Each item:

- `doc_id`: as given above.
- `page`: the 1-based position of the page in the PDF FILE (first page of the file = 1).
  This may differ from the page number printed on the page; always use the file position.
- `evidence_quote`: a quote copied EXACTLY from that page, character for character,
  25 words or fewer. Pick the shortest span that contains the answer (a sentence or a
  table row). Do not fix typos, do not change numbers, do not join two places with "...".
  For a numerical question that needs a calculation, quote each number you use.
  For a table, quote one row or a short run of cells as the text reads.

If you cannot give an exact quote and an exact page, do not write the question.
For `unanswerable_*` and `ambiguous` questions, `gold` is an empty list.

## Reference answer

One or two sentences using only what the evidence says. Include units and the year or
section. For a calculation, show it briefly ("6.1 - 5.4 = 0.7"). For holistic questions,
list the 3 to 5 points a good answer must contain. For unanswerable questions, write what a
correct system should do (for example: "Not stated in the document; the report covers 2025
only."). For `unanswerable_near`, put in `notes` what the document does say on the topic and
the page where it does. For `ambiguous`, put in `notes` the clarifying question to ask.

## Output format

Return ONLY JSON Lines: one object per line, no code fences, no text before or after.

{"id": "{{DOC_ID}}-001", "question": "...", "type": "direct_fact", "format": "text",
 "behaviour": "answerable", "reference_answer": "...",
 "gold": [{"doc_id": "{{DOC_ID}}", "page": 12, "evidence_quote": "..."}],
 "source": "generated", "notes": ""}

- `id`: `{{DOC_ID}}-NNN`, numbered from 001.
- `source`: always "generated".
- Do NOT include `split` or `answerable` fields.

## Counts for this document

{{COUNTS}}

If the document has no good material for one of them (for example no tables), write fewer
and say so in `notes` of the last line.

## Final self-check before you answer

For each line: (1) is the quote really on that file page, copied exactly? (2) does the quote
alone support the reference answer? (3) does the question avoid the document's own wording
and avoid references like "this document"? (4) for `unanswerable_near`, did you search the
document for the detail and confirm it is not there? Drop any item that fails.

---- END PROMPT ----

## Counts per call (about 96 candidates in total, for roughly 60 to 70 kept answerable)

Use the abbreviations expanded in `{{COUNTS}}`, for example "direct_fact 3, numerical 4,
temporal 4, comparative 4, spanning 3, relationship 3, holistic 2, unanswerable_out 2,
unanswerable_near 2, ambiguous 1; at least a quarter of the answerable ones with
format table, if the document has tables".

| doc | direct_fact | numerical | temporal | comparative | spanning | relationship | holistic | unans_out | unans_near | ambiguous | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| equinor_ar2025 | 3 | 4 | 4 | 4 | 3 | 3 | 2 | 2 | 2 | 1 | 28 |
| irena_rpgc2024 | 2 | 3 | 3 | 3 | 2 | 2 | 1 | 2 | 1 | 1 | 20 |
| each Havtil regulation (x4) | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 9 |
| cross-document (below) | | | | 4 | 4 | 4 | | | | | 12 |

Totals: direct_fact 13, numerical 11, temporal 11, comparative 15, spanning 13,
relationship 13, holistic 3, unanswerable_out 8, unanswerable_near 7, ambiguous 2 = 96.
For the Havtil regulations, `numerical` means thresholds, limits and time periods
(hours, days, percentages), and `temporal` means dates, deadlines and transitional rules.

## Cross-document variant (attach the relevant PDFs together)

Same prompt, with these changes: replace "Your document" with the list of attached
documents and their doc_ids (`equinor_ar2025`, `havtil_framework`, `havtil_management`,
`havtil_activities`, `havtil_co2`, `irena_rpgc2024`); write only `comparative`, `spanning`
and `relationship` questions, all `answerable`; every `gold` list must contain items from at
least two different `doc_id`s; ids are `cross-NNN`. Pairs worth trying: Havtil Management or
Activities with Equinor's safety sections; IRENA cost figures with Equinor's renewables
figures; two Havtil regulations that refer to each other.
