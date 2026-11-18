# Question-generation prompt, round 2 (harder questions)

Round 1 (`question_gen_prompt.md`) produced 84 valid but easy questions: 56 of 67 answerable
ones need one page, and most reuse distinctive words of their evidence. Round 2 asks for
harder ones. Do not fill the placeholders by hand: `python eval/build_prompts.py` writes one
ready-to-paste file per call into `eval/prompts/`. Everything between BEGIN and END is the
template; the schema, evidence rules and output format are the same as round 1.

Round-2 questions are deliberately worded differently from their evidence. Report results by
round (ids 001 to 099 = round 1, 101+ = round 2): it is a different difficulty tier, not
more of the same, and the README must say how each tier was produced.

---- BEGIN PROMPT ----

You are helping build an evaluation set for a retrieval-augmented question answering system
over six public documents. This is the SECOND round. The first round produced questions that
were too easy: each could be answered by finding one sentence that shares unusual words with
the question. Your job now is to write questions that a careful reader could answer from the
attached document, but that a keyword search would find hard. A human will review every item
and a script will check every quote against the document text.

## Your document

- doc_id: {{DOC_ID}}
- title: {{TITLE}}
- The attached text marks every page with a line `##### PAGE N ({{DOC_ID}}) #####`.
  `page` in your output is that N.

## What makes a question hard (required, and checked by a script)

1. **Different words from the evidence.** The question must share few words with the quote(s)
   that answer it. Describe things by what they are or do instead of using the document's
   labels: not "What is the LEX12h limit?" but "What is the highest average sound exposure
   allowed over a working day?". Do not use section numbers, table or figure numbers, or
   exact figures from the answer. Use a synonym or a description wherever a natural one
   exists. Names of the company or regulation are fine.
2. **Evidence on two or more pages** for every `spanning`, `relationship` and `comparative`
   question (the pages must be different and each quote must be NEEDED for the answer; a
   quote that merely repeats the other does not count).
3. **A real calculation** for every `numerical` question: a difference, ratio, sum, percentage
   or rate that needs two or more stated numbers (quote each number). A single stated
   figure is NOT numerical; it is a direct fact and is not wanted this round.
4. **No direct_fact questions** this round, and no question that is answered by one sentence.
5. Must still be natural: something a real user would ask, with one clear answer in the text.
   Do not write trick questions, riddles or questions that need outside knowledge.
6. Forbidden: starting with "Under the ... Regulations" or "According to ..."; any reference
   to the document's layout ("the table above", "the summary", "on page N", "in this
   document"); questions on the same fact as one in the list below.

## Questions already written (do NOT duplicate their topic or fact)

{{EXISTING_QUESTIONS}}

## Types, format, behaviour

`type`: numerical | temporal | comparative | spanning | relationship | holistic
(definitions as in round 1: numerical = needs a calculation; temporal = date, period,
sequence or change over time; comparative = compares entities, years or requirements;
spanning = needs several places; relationship = cause, dependency or who-owes-what;
holistic = overview of a theme, with 2 to 5 evidence quotes and a list of the points a good
answer needs).

`format`: "text" or "table" (table only if the table text is selectable).

`behaviour`: "answerable" or "unanswerable_near". A near-miss must be a hard one: the document
discusses the exact topic, gives nearby numbers, dates or entities that could be mistaken for
the answer, but does not state the specific thing asked. Put in `notes` what it does say and
the page(s). Before writing one, search the whole text for the detail and confirm it is
absent. Do not write unanswerable_out or ambiguous questions this round.

## Evidence rules (checked by a script; unchanged)

For every answerable question give 1 to 4 evidence items (holistic: 2 to 5), each with
`doc_id`, `page` (the N of the PAGE marker) and `evidence_quote`: copied EXACTLY from that
page, plain words without markdown symbols such as # | *, at most 25 words, the shortest span
that contains what you need. If a calculation needs a number from a table, quote that row.
For `unanswerable_near`, `gold` is an empty list.

## Reference answer

One or two sentences using only what the evidence says, with units and year or section. For a
calculation show it ("6.1 - 5.4 = 0.7"). For holistic, list the 3 to 5 points a good answer
must contain. For near-misses write what a correct system should say, for example "Not
stated; the document gives X on page N but not Y."

## Output format

Return ONLY JSON Lines, one object per line, no code fences, no commentary:

{"id": "{{DOC_ID}}-101", "question": "...", "type": "numerical", "format": "text",
 "behaviour": "answerable", "reference_answer": "...",
 "gold": [{"doc_id": "{{DOC_ID}}", "page": 12, "evidence_quote": "..."}],
 "source": "generated", "notes": ""}

Number ids from 101. Do NOT include `split` or `answerable` fields.

## Counts for this document

{{COUNTS}}

If the document has no good material for one of them, write fewer and say why in `notes` of
the last line. Spread the questions across the whole document; do not cluster them.

## Self-check before you answer

For each line: (1) quotes exact and on that page? (2) do the quotes together support the
answer, and is each one needed? (3) count the words the question shares with the quotes
(ignoring "the", "of", "what" and similar); if more than a third of the question's words
appear in the quotes, reword it; (4) numerical: does it need arithmetic? spanning,
relationship, comparative: are the pages different? (5) near-miss: did you search for the
detail and confirm it is missing? Drop any item that fails.

---- END PROMPT ----

## Counts per call (about 65 candidates)

| call | numerical | temporal | comparative | spanning | relationship | holistic | near-miss | total |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| equinor_ar2025 (attach in 3 page ranges, scale counts) | 3 | 2 | 3 | 3 | 2 | 1 | 2 | 16 |
| irena_rpgc2024 | 2 | 1 | 2 | 2 | 2 | 1 | 1 | 11 |
| each Havtil regulation (x4) | 1 | 1 | 1 | 2 | 1 | 0 | 1 | 7 |
| cross-document (below) | | | 4 | 3 | 3 | | | 10 |

## Cross-document variant

Same template with these changes: attach the relevant documents together (each page marker
carries its own doc_id); write only comparative, spanning and relationship questions, all
answerable; every question needs evidence from at least two different doc_ids; ids
`cross-101`...; rules 1 to 6 apply. `build_prompts.py` fills in the pairs.
