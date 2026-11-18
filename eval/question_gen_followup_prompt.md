# Round-2 follow-up prompt (paste into the SAME session that produced round 1)

Use this in the per-document session that already has the document and its round-1 output.
Replace `{{COUNTS}}` with the line for that document from the table at the bottom, and
`{{DOC_ID}}` with its doc_id. Save the reply as `output/Output/<doc_id>_r2.jsonl`.
Cross-document questions are a separate call (see `build_prompts.py`).

---- BEGIN PROMPT ----

Thanks. The questions you just wrote are valid, but they are too easy for my purpose: most
can be answered from one sentence on one page, and many share unusual words with their
evidence (names, section numbers, exact terms), so a plain keyword search finds them. Write a
SECOND batch for the same document ({{DOC_ID}}) that is harder. Use the same document, the
same page numbering and the same evidence rules and JSONL format as before. Do not repeat any
topic or fact from your first batch.

## What makes a question hard (required)

1. **Different words from the evidence.** The question must share few words with the quote(s)
   that answer it. Describe things by what they are or do instead of using the document's
   labels. Example: not "What is the LEX12h limit?" but "What is the highest average sound
   exposure allowed over a working day?". Do not use section numbers, table or figure numbers,
   or exact figures from the answer. Use a natural synonym or description wherever one exists.
   Company and regulation names are fine.
2. **Evidence on two or more different pages** for every `spanning`, `relationship` and
   `comparative` question. Each quote must be NEEDED for the answer; a quote that only repeats
   another does not count.
3. **A real calculation** for every `numerical` question: a difference, ratio, sum, percentage
   or rate from two or more stated numbers. Quote each number you use. A single stated figure
   is a direct fact and is not wanted in this batch.
4. **No `direct_fact` questions**, and no question that one sentence answers.
5. **Natural:** something a real user would ask, with one clear answer in the text. No tricks,
   riddles or outside knowledge.
6. **Forbidden:** starting with "Under the ... Regulations" or "According to ..."; any reference
   to layout or location ("the table above", "the summary", "on page N", "in this document",
   "in the report").

## Types and behaviour

`type`: numerical | temporal | comparative | spanning | relationship | holistic (same
definitions as before; holistic = overview of a theme, 2 to 5 evidence quotes, and the 3 to 5
points a good answer needs in `reference_answer`).
`format`: "text" or "table" (table only when the table text is selectable).
`behaviour`: "answerable" or "unanswerable_near". A near-miss must be a hard one: the document
discusses the exact topic and gives nearby numbers, dates or entities that could be mistaken
for the answer, but does not state the specific thing asked. Search the whole document and
confirm the detail is absent before you write it; put what the document does say, and the
page(s), in `notes`. No `unanswerable_out` or `ambiguous` questions in this batch.

## Counts

{{COUNTS}}

If the document lacks good material for one of them, write fewer and say why in `notes` of
the last line. Spread the questions across the whole document.

## Output

JSON Lines only, no code fences, no commentary. Same fields as before. Number the ids from
101 (`{{DOC_ID}}-101`, `-102`, ...). Do not include `split` or `answerable`.

## Check before you answer

For each line: (1) is every quote exact and on that page? (2) do the quotes together support
the answer, and is each one needed? (3) does more than a third of the question's content
words (ignoring "the", "of", "what" and similar) appear in the quotes? If so, reword it.
(4) numerical: does it need arithmetic? spanning, relationship, comparative: are the pages
different? (5) near-miss: did you confirm the detail is absent? Drop any item that fails.

---- END PROMPT ----

## Counts line per document

| doc_id | paste as {{COUNTS}} |
| --- | --- |
| equinor_ar2025 | numerical 3, temporal 2, comparative 3, spanning 3, relationship 2, holistic 1, unanswerable_near 2 (16 in total) |
| irena_rpgc2024 | numerical 2, temporal 1, comparative 2, spanning 2, relationship 2, holistic 1, unanswerable_near 1 (11 in total) |
| havtil_framework, havtil_management, havtil_activities, havtil_co2 | numerical 1, temporal 1, comparative 1, spanning 2, relationship 1, unanswerable_near 1 (7 in total) |
