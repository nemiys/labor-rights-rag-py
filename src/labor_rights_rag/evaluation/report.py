"""The evaluation report, as Markdown."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date

from labor_rights_rag.evaluation.metrics import ThresholdRow, hit_at
from labor_rights_rag.evaluation.runner import (
    MODES,
    GenerationRow,
    RetrievalRow,
    summarize_retrieval,
)


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def retrieval_report(
    rows: Sequence[RetrievalRow],
    sweep: Sequence[ThresholdRow],
    split: str,
    current_threshold: float,
) -> str:
    by_mode = {m: [r for r in rows if r.mode == m] for m in MODES}
    focus = "hybrid_bm25" if by_mode["hybrid_bm25"] else "hybrid"
    n = len(by_mode[focus])
    lines = [
        f"# Retrieval evaluation ({date.today()}, split: {split}, {n} answerable questions)",
        "",
        "A chunk counts when it belongs to an expected section. Hit@k: the share of questions "
        "with such a chunk in the first k. MRR is within the first 10. Recall@5: the share of the "
        "expected sections found in the first 5.",
        "",
        "| Mode | Hit@1 | Hit@3 | Hit@5 | MRR | Recall@5 |",
        "|---|---|---|---|---|---|",
    ]
    for mode in MODES:
        s = summarize_retrieval(by_mode[mode])
        lines.append(
            f"| {mode} | {_pct(s.hit1)} | {_pct(s.hit3)} | {_pct(s.hit5)} "
            f"| {s.mrr:.3f} | {_pct(s.recall5)} |"
        )

    categories = sorted({r.question.category for r in rows})
    lines += [
        "",
        "## By question type (Hit@5 / MRR)",
        "",
        "| Type | n | " + " | ".join(MODES) + " |",
    ]
    lines.append("|---|---|" + "---|" * len(MODES))
    for category in categories:
        cells = []
        for mode in MODES:
            s = summarize_retrieval([r for r in by_mode[mode] if r.question.category == category])
            cells.append(f"{_pct(s.hit5)} / {s.mrr:.2f}")
        size = len([r for r in by_mode[focus] if r.question.category == category])
        lines.append(f"| {category} | {size} | " + " | ".join(cells) + " |")

    ranks: dict[str, dict[str, int | None]] = defaultdict(dict)
    for r in rows:
        ranks[r.question.id][r.mode] = r.rank
    questions = {r.question.id: r.question for r in rows}
    misses = [qid for qid in ranks if not hit_at(ranks[qid].get(focus), 5)]
    lines += ["", f"## Misses of {focus}: not in the first 5 ({len(misses)})", ""]
    lines += [
        "| Id | " + " | ".join(MODES) + " | Question |",
        "|---|" + "---|" * len(MODES) + "---|",
    ]
    for qid in misses:
        found = ranks[qid]
        cells = [str(found.get(m) or "-") for m in MODES]
        lines.append(f"| {qid} | " + " | ".join(cells) + f" | {questions[qid].question} |")

    lines += [
        "",
        "## Refusal threshold (closest-chunk similarity)",
        "",
        f"What a refusal below each value would do. The current setting is {current_threshold}.",
        "",
        "| Threshold | Answerable refused | Unanswerable passed to the model |",
        "|---|---|---|",
    ]
    lines += [
        f"| {row.threshold:.2f} | {_pct(row.false_refusals)} "
        f"| {_pct(row.answered_without_source)} |"
        for row in sweep
    ]
    return "\n".join(lines) + "\n"


def _share(count: int, total: int) -> str:
    return f"{_pct(count / total)} ({count}/{total})" if total else "-"


def generation_report(
    rows: Sequence[GenerationRow], model: str, split: str, condition: str = "system"
) -> str:
    answerable = [r for r in rows if r.question.answerable]
    unanswerable = [r for r in rows if not r.question.answerable]
    called = [r for r in unanswerable if r.result]
    results = [r.result for r in rows if r.result]
    seconds = [x.seconds for x in results]
    costs = [x.cost_usd for x in results if x.cost_usd is not None]

    table = [
        (
            "Answerable questions answered",
            _share(sum(r.answered for r in answerable), len(answerable)),
        ),
        (
            "Answers with every expected fact",
            _share(sum(r.facts_ok for r in answerable), len(answerable)),
        ),
        (
            "Answers citing an expected section",
            "not applicable (no sources)"
            if condition == "closed_book"
            else _share(sum(r.citation_ok for r in answerable), len(answerable)),
        ),
        (
            "Unanswerable questions refused",
            _share(sum(not r.answered for r in called), len(called)),
        ),
        (
            "Unanswerable questions answered anyway",
            _share(sum(r.answered for r in called), len(called)),
        ),
        ("Mean seconds per question", f"{sum(seconds) / len(seconds):.1f}" if seconds else "-"),
        (
            "Tokens in / out",
            f"{sum(x.input_tokens for x in results)} / {sum(x.output_tokens for x in results)}",
        ),
        ("Cost in dollars", f"{sum(costs):.4f}" if costs else "not priced (a free model)"),
    ]
    lines = [
        f"# Generation evaluation ({date.today()}, model: {model}, split: {split}, "
        f"condition: {condition})",
        "",
        f"Questions: {len(rows)}, of which {len(answerable)} answerable. "
        f"Calls that failed: {sum(r.result is None for r in rows)}.",
        "",
        "| Measure | Result |",
        "|---|---|",
        *[f"| {name} | {value} |" for name, value in table],
        "",
        "## Where the answer was wrong or missing",
        "",
        "| Id | Status | Facts | Citation | Question |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        right = r.facts_ok and (r.citation_ok or condition == "closed_book")
        bad = not right if r.question.answerable else r.answered
        if bad:
            status = r.result.status if r.result else f"ERROR {r.error}"
            facts, cite = ("yes" if r.facts_ok else "no"), ("yes" if r.citation_ok else "no")
            lines.append(
                f"| {r.question.id} | {status} | {facts} | {cite} | {r.question.question} |"
            )
    return "\n".join(lines) + "\n"


def answers_report(rows: Sequence[GenerationRow], model: str) -> str:
    """Every answer in full and what it cites, to read by hand: is each claim in its source."""
    lines = [
        f"# Answers to read ({date.today()}, model: {model})",
        "",
        "For each answer: does every claim appear in the quoted source? Mark each one.",
        "",
    ]
    for r in rows:
        q = r.question
        expected = ", ".join(f"{e.law}:{e.section}" for e in q.expected) or "none (not answerable)"
        lines += [f"## {q.id} {q.category}", "", f"**Question:** {q.question}", ""]
        lines.append(f"**Expected sections:** {expected}")
        if r.result is None:
            lines += [f"**Call failed:** {r.error}", ""]
            continue
        lines += [
            f"**Status:** {r.result.status}. Facts found: {r.facts_ok}. "
            f"Citation right: {r.citation_ok}.",
            "",
            f"**Answer:** {r.result.answer}",
            "",
        ]
        for c in r.result.citations:
            lines.append(f"- [{c.number}] {c.card.law_id}:{c.card.section}: {c.card.quote[:200]}")
        lines.append("")
    return "\n".join(lines) + "\n"
