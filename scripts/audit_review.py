#!/usr/bin/env python3
"""Lightweight structural audit for a Chinese economics/management review.

The checks cover citation ordering, repeated citations, citation-island
streaks, empty transitions, paragraph count, author-by-author listing, and
surface signs of list-like parallel prose and repeated meta-narration. They do
not verify sentence-level logic, naturalness, or whether sources support claims.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


NUMERIC_CITATION = re.compile(r"\[((?:\d+\s*(?:[-,，–]\s*)?)+)\]")
AUTHOR_YEAR = re.compile(r"[A-Za-z\u4e00-\u9fff·.]{1,30}(?:等|et\s+al\.)?\s*[（(](?:19|20)\d{2}[）)]", re.I)
CONTRAST = ("但", "然而", "相反", "不同", "相比", "一致", "争议", "边界", "条件")
EMPTY_TRANSITIONS = (
    "进一步",
    "与此同时",
    "在此基础上",
    "随着研究深入",
    "沿着这一逻辑",
    "此外",
)
PARALLEL_PATTERNS = (
    ("一方面…另一方面", re.compile(r"一方面.+?另一方面")),
    ("既…又/也", re.compile(r"既.+?(?:又|也)")),
    ("不仅…而且", re.compile(r"不仅.+?而且")),
    ("首先…其次/最后", re.compile(r"首先.+?(?:其次|最后)")),
)
META_NARRATOR_TERMS = ("研究", "文献", "证据", "结论", "问题", "路径")
META_NARRATOR_ACTIONS = ("推进", "延伸", "引向", "拓展", "形成", "演进")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])")


def expand_numbers(raw: str) -> list[int]:
    values: list[int] = []
    for part in re.split(r"[,，]", raw):
        part = part.strip()
        match = re.fullmatch(r"(\d+)\s*[-–]\s*(\d+)", part)
        if match:
            start, end = map(int, match.groups())
            step = 1 if end >= start else -1
            values.extend(range(start, end + step, step))
        elif part.isdigit():
            values.append(int(part))
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a literature-review text file.")
    parser.add_argument("input", type=Path, help="UTF-8 .txt or .md file")
    parser.add_argument(
        "--expect-single-paragraph",
        action="store_true",
        help="Fail when the review contains more than one paragraph.",
    )
    parser.add_argument(
        "--single-use-citations",
        action="store_true",
        help="Fail when a numeric source is cited more than once.",
    )
    parser.add_argument(
        "--strict-linear-flow",
        action="store_true",
        help="Fail only when transition, parallel-list, or meta-narration risks are dense.",
    )
    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

    first_seen: list[int] = []
    citation_counts: dict[int, int] = {}
    for match in NUMERIC_CITATION.finditer(text):
        for number in expand_numbers(match.group(1)):
            citation_counts[number] = citation_counts.get(number, 0) + 1
            if number not in first_seen:
                first_seen.append(number)

    missing: list[int] = []
    if first_seen:
        missing = sorted(set(range(min(first_seen), max(first_seen) + 1)) - set(first_seen))

    listing_risks: list[tuple[int, int]] = []
    uncited_paragraphs: list[int] = []
    for index, paragraph in enumerate(paragraphs, start=1):
        author_count = len(AUTHOR_YEAR.findall(paragraph))
        if author_count >= 3 and not any(word in paragraph for word in CONTRAST):
            listing_risks.append((index, author_count))
        if len(paragraph) >= 80 and not NUMERIC_CITATION.search(paragraph) and not AUTHOR_YEAR.search(paragraph):
            uncited_paragraphs.append(index)

    sentences = [s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip()]
    single_source_sentence = []
    empty_transition_hits: list[tuple[int, str]] = []
    parallel_structure_hits: list[tuple[int, str]] = []
    semicolon_stack_hits: list[tuple[int, int]] = []
    meta_narrator_hits: list[int] = []
    for index, sentence in enumerate(sentences, start=1):
        citations = [
            number
            for match in NUMERIC_CITATION.finditer(sentence)
            for number in expand_numbers(match.group(1))
        ]
        single_source_sentence.append(len(set(citations)) == 1)
        for phrase in EMPTY_TRANSITIONS:
            if phrase in sentence:
                empty_transition_hits.append((index, phrase))
        for label, pattern in PARALLEL_PATTERNS:
            if pattern.search(sentence):
                parallel_structure_hits.append((index, label))
        semicolon_count = sentence.count("；") + sentence.count(";")
        if semicolon_count:
            semicolon_stack_hits.append((index, semicolon_count))
        opening = sentence[:24]
        if any(term in opening for term in META_NARRATOR_TERMS) and any(
            action in sentence for action in META_NARRATOR_ACTIONS
        ):
            meta_narrator_hits.append(index)

    citation_island_streaks: list[tuple[int, int]] = []
    start: int | None = None
    for index, is_single in enumerate(single_source_sentence + [False], start=1):
        if is_single and start is None:
            start = index
        elif not is_single and start is not None:
            if index - start >= 3:
                citation_island_streaks.append((start, index - 1))
            start = None

    repeated_citations = {
        number: count for number, count in sorted(citation_counts.items()) if count > 1
    }

    expected_order = sorted(first_seen)
    print(f"Characters: {len(text)}")
    print(f"Paragraphs: {len(paragraphs)}")
    print(f"Numeric citations in first-appearance order: {first_seen or 'none'}")
    print(f"Citation order is ascending: {first_seen == expected_order}")
    print(f"Missing numbers within observed range: {missing or 'none'}")
    print(f"Repeated numeric citations: {repeated_citations or 'none'}")
    print(f"Consecutive one-source sentence streaks: {citation_island_streaks or 'none'}")
    print(f"Potentially empty transition markers: {empty_transition_hits or 'none'}")
    print(f"Potential list-like parallel structures: {parallel_structure_hits or 'none'}")
    print(f"Sentences containing semicolons: {semicolon_stack_hits or 'none'}")
    print(f"Potential meta-narrator sentences: {meta_narrator_hits or 'none'}")
    print(f"Possible author-by-author listing paragraphs: {listing_risks or 'none'}")
    print(f"Long paragraphs without detected citations: {uncited_paragraphs or 'none'}")
    print("Note: this audit cannot verify source existence, claim support, or citation truth.")
    failed = False
    if args.expect_single_paragraph and len(paragraphs) != 1:
        print(f"FAIL: expected one paragraph, found {len(paragraphs)}.")
        failed = True
    if args.single_use_citations and repeated_citations:
        print("FAIL: one or more numeric sources were cited more than once.")
        failed = True
    dense_surface_risk = (
        len(empty_transition_hits) >= 3
        or len(parallel_structure_hits) >= 3
        or any(count >= 2 for _, count in semicolon_stack_hits)
        or len(meta_narrator_hits) >= 3
    )
    if args.strict_linear_flow and dense_surface_risk:
        print("FAIL: strict linear-flow checks found dense template or list-like prose risks.")
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
