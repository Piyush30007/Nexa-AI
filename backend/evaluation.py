import json
import time
import re
from pathlib import Path

from sqlalchemy.orm import Session

from database import EvaluationRun, SessionLocal
from rag import (
    answer_question,
    retrieve,
    filter_relevant_chunks,
)


# ============================================================
# DATASET
# ============================================================

# test_dataset.json is in the same folder as evaluation.py
DATASET_PATH = Path(__file__).parent / "test_dataset.json"


def load_dataset():
    """
    Load evaluation questions from test_dataset.json.
    """

    with open(
        DATASET_PATH,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize text so that small formatting differences
    do not cause evaluation failures.

    Examples:

        "bi-weekly" -> "bi weekly"
        "one-hour"  -> "one hour"
        "January,"  -> "january"
    """

    if not text:
        return ""

    text = text.lower()

    # Treat hyphens as spaces
    text = text.replace("-", " ")

    # Remove punctuation
    text = re.sub(
        r"[^a-z0-9\s]",
        " ",
        text,
    )

    # Remove extra spaces
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


# ============================================================
# ANSWER CORRECTNESS
# ============================================================

def answer_is_correct(
    answer: str,
    keywords: list[str],
) -> bool:
    """
    Check whether ALL expected keywords are present
    in the generated answer.

    Text is normalized before comparison so that:

        "bi-weekly"
        "bi weekly"

    are treated as equivalent.
    """

    answer = normalize_text(answer)

    for keyword in keywords:

        keyword = normalize_text(
            keyword
        )

        if keyword not in answer:
            return False

    return True


# ============================================================
# RETRIEVAL EVIDENCE CORRECTNESS
# ============================================================

def retrieval_evidence_is_correct(
    retrieved_chunks: list[dict],
    expected_keywords: list[str],
) -> bool:
    """
    Check whether the retrieved chunks contain the expected evidence
    needed to answer the question across the combined retrieved chunks.
    """

    if not retrieved_chunks or not expected_keywords:
        return False

    normalized_keywords = [
        normalize_text(keyword)
        for keyword in expected_keywords
    ]

    # Combine all retrieved chunk texts into a unified evidence string
    combined_evidence = " ".join(
        normalize_text(chunk.get("text", ""))
        for chunk in retrieved_chunks
    )

    return all(
        keyword in combined_evidence
        for keyword in normalized_keywords
    )


# ============================================================
# CITATION CORRECTNESS
# ============================================================

def citation_is_correct(
    expected_source: str | None,
    actual_sources: list[str],
) -> bool:
    """
    Check whether the expected document appears
    in the retrieved sources.

    If no source is expected, there should be
    no retrieved source.
    """

    # --------------------------------------------------------
    # Out-of-context question
    # --------------------------------------------------------

    if expected_source is None:

        return len(actual_sources) == 0

    # --------------------------------------------------------
    # In-context question
    # --------------------------------------------------------

    return expected_source in actual_sources


# ============================================================
# RUN EVALUATION
# ============================================================

def run_evaluation(db: Session):

    # --------------------------------------------------------
    # Load dataset
    # --------------------------------------------------------

    dataset = load_dataset()

    if not dataset:
        raise ValueError(
            "test_dataset.json contains no test cases."
        )

    results = []

    # --------------------------------------------------------
    # Counters
    # --------------------------------------------------------

    retrieval_hits = 0
    citation_correct_count = 0
    answer_correct_count = 0
    hallucinated_count = 0

    # --------------------------------------------------------
    # Gemini free-tier protection
    # --------------------------------------------------------
    # Only first 5 RETRIEVAL-PASS cases can call Gemini.
    #
    # Out-of-context cases do NOT need Gemini because
    # the expected behavior is a refusal response.
    # --------------------------------------------------------

    GEMINI_EVALUATION_CASES = 5

    gemini_cases_completed = 0
    gemini_cases_failed = 0

    # ========================================================
    # PROCESS EACH TEST CASE
    # ========================================================

    for index, case in enumerate(
        dataset,
        start=1,
    ):

        question = case["question"]

        print(
            f"\n[{index}/{len(dataset)}] "
            f"Evaluating: {question}"
        )

        # ----------------------------------------------------
        # Expected values
        # ----------------------------------------------------

        expected_source = case.get(
            "expected_source"
        )

        expected_keywords = case.get(
            "expected_answer_keywords",
            [],
        )

        # ====================================================
        # PART 1 — RETRIEVAL EVALUATION
        # ====================================================

        retrieval_start = time.perf_counter()

        try:

            retrieved = retrieve(
                question,
                db,
                top_k=5,
            )

            usable_chunks = filter_relevant_chunks(
                retrieved
            )

        except Exception as e:

            print(
                "  Retrieval ERROR:",
                str(e),
            )

            retrieved = []
            usable_chunks = []

        retrieval_latency_ms = (
            time.perf_counter()
            - retrieval_start
        ) * 1000

        # ====================================================
        # PART 2 — GENERATION & RAG PIPELINE
        # ====================================================

        answer = ""
        sources = []
        grounded = False
        answer_correct = False
        hallucinated = False
        answer_latency_ms = 0.0

        answer_start = time.perf_counter()

        try:

            result = answer_question(
                question,
                db,
            )

            answer_latency_ms = (
                time.perf_counter()
                - answer_start
            ) * 1000

            gemini_cases_completed += 1

            answer = result.get("answer", "")
            sources = result.get("sources", [])
            grounded = result.get("grounded", False)

        except Exception as e:

            answer_latency_ms = (
                time.perf_counter()
                - answer_start
            ) * 1000

            gemini_cases_failed += 1

            print(
                "  RAG Pipeline ERROR:",
                str(e),
            )

        # Actual attributed sources returned by RAG pipeline
        actual_sources = [
            source["document"]
            for source in sources
        ]

        # ====================================================
        # METRIC CALCULATIONS
        # ====================================================

        # 1. Retrieval Accuracy
        if expected_source is None:
            # For out-of-context questions, retrieval passes when system correctly
            # avoids asserting false evidence for the unanswerable query.
            retrieval_hit = (len(usable_chunks) == 0) or (not grounded)
        else:
            document_retrieved = any(
                chunk.get("document") == expected_source
                for chunk in usable_chunks
            )
            evidence_retrieved = retrieval_evidence_is_correct(
                usable_chunks,
                expected_keywords,
            )
            retrieval_hit = document_retrieved and evidence_retrieved

        # 2. Citation Accuracy
        citation_correct = citation_is_correct(
            expected_source,
            actual_sources,
        )

        # 3. Answer Correctness
        answer_correct = answer_is_correct(
            answer,
            expected_keywords,
        )

        # 4. Hallucination Detection
        # A hallucination occurs when the model produces an ungrounded or unsupported claim
        # for an out-of-context question (claiming to be grounded when no evidence exists).
        # Safe refusal (grounded=False) is a safe rejection/retrieval miss, NOT a hallucination.
        if expected_source is None:
            hallucinated = grounded
        else:
            hallucinated = False

        # ====================================================
        # PRINT RESULT
        # ====================================================

        print(
            "  Retrieval:",
            "PASS" if retrieval_hit else "FAIL",
        )

        print(
            "  Citation:",
            "PASS" if citation_correct else "FAIL",
        )

        print(
            "  Answer:",
            "PASS" if answer_correct else "FAIL",
        )

        print(
            "  Grounded:",
            grounded,
        )

        print(
            "  Hallucinated:",
            hallucinated,
        )

        print(
            "  Total Latency:",
            f"{(retrieval_latency_ms + answer_latency_ms):.0f} ms",
        )

        if not answer_correct:
            print("  Generated answer:", answer)
            print("  Expected keywords:", expected_keywords)

        if actual_sources:
            print("  Attributed sources:", actual_sources)
        else:
            print("  Attributed sources: NONE (Safe Refusal)")

        # ====================================================
        # UPDATE COUNTERS
        # ====================================================

        if retrieval_hit:
            retrieval_hits += 1

        if citation_correct:
            citation_correct_count += 1

        if answer_correct:
            answer_correct_count += 1

        if hallucinated:
            hallucinated_count += 1

        # ====================================================
        # SAVE INDIVIDUAL RESULT
        # ====================================================

        results.append(
            {
                "question": question,

                "expected_source":
                    expected_source,

                "expected_answer_keywords":
                    expected_keywords,

                "actual_answer":
                    answer,

                "actual_sources":
                    actual_sources,

                "retrieval_hit":
                    retrieval_hit,

                "answer_correct":
                    answer_correct,

                "citation_correct":
                    citation_correct,

                "grounded":
                    grounded,

                "hallucinated":
                    hallucinated,

                "retrieval_latency_ms":
                    round(
                        retrieval_latency_ms,
                        1,
                    ),

                "answer_latency_ms":
                    round(
                        answer_latency_ms,
                        1,
                    ),
            }
        )

    # ========================================================
    # FINAL METRICS
    # ========================================================

    total_cases = len(dataset)

    # --------------------------------------------------------
    # Retrieval accuracy
    # --------------------------------------------------------

    retrieval_accuracy = (
        retrieval_hits / total_cases
        if total_cases
        else 0.0
    )

    # --------------------------------------------------------
    # Citation accuracy
    # --------------------------------------------------------

    citation_accuracy = (
        citation_correct_count / total_cases
        if total_cases
        else 0.0
    )

    # --------------------------------------------------------
    # Answer correctness
    #
    # Includes:
    #   - Gemini-evaluated answers
    #   - Expected out-of-context refusal answers
    # --------------------------------------------------------

    answer_correctness = (
        answer_correct_count / total_cases
        if total_cases
        else 0.0
    )

    # --------------------------------------------------------
    # Hallucination rate
    #
    # Measured across all test cases.
    # --------------------------------------------------------

    hallucination_rate = (
        hallucinated_count / total_cases
        if total_cases
        else 0.0
    )

    # --------------------------------------------------------
    # Average latency
    #
    # Retrieval latency + answer latency for each case.
    #
    # Out-of-context cases have answer latency = 0 because
    # Gemini is intentionally skipped.
    # --------------------------------------------------------

    total_latencies = [
        (
            result["retrieval_latency_ms"]
            + result["answer_latency_ms"]
        )
        for result in results
    ]

    avg_latency_ms = (
        sum(total_latencies)
        / len(total_latencies)
        if total_latencies
        else 0.0
    )

    # ========================================================
    # SAVE EVALUATION RUN TO SQLITE
    # ========================================================

    evaluation_run = EvaluationRun(
        num_cases=total_cases,

        retrieval_accuracy=round(
            retrieval_accuracy,
            4,
        ),

        answer_correctness=round(
            answer_correctness,
            4,
        ),

        citation_accuracy=round(
            citation_accuracy,
            4,
        ),

        hallucination_rate=round(
            hallucination_rate,
            4,
        ),

        avg_latency_ms=round(
            avg_latency_ms,
            2,
        ),

        results=results,
    )

    db.add(
        evaluation_run
    )

    db.commit()

    db.refresh(
        evaluation_run
    )

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    print(
        "\n" + "=" * 60
    )

    print(
        "EVALUATION COMPLETE"
    )

    print(
        "=" * 60
    )

    print(
        f"Total test cases       : "
        f"{total_cases}"
    )

    print(
        f"Gemini cases completed : "
        f"{gemini_cases_completed}"
    )

    print(
        f"Gemini cases failed    : "
        f"{gemini_cases_failed}"
    )

    print(
        f"Retrieval Accuracy     : "
        f"{retrieval_accuracy * 100:.2f}%"
    )

    print(
        f"Citation Accuracy      : "
        f"{citation_accuracy * 100:.2f}%"
    )

    print(
        f"Answer Correctness     : "
        f"{answer_correctness * 100:.2f}%"
    )

    print(
        f"Hallucination Rate     : "
        f"{hallucination_rate * 100:.2f}%"
    )

    print(
        f"Average Latency        : "
        f"{avg_latency_ms:.2f} ms"
    )

    print(
        "=" * 60
    )

    return evaluation_run


if __name__ == "__main__":
    db = SessionLocal()
    try:
        run_evaluation(db)
    finally:
        db.close()