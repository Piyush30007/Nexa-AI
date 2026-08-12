import json
import time
import re
from pathlib import Path

from sqlalchemy.orm import Session

from database import EvaluationRun
from rag import answer_question, retrieve , filter_relevant_chunks


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
    Check whether the retrieved chunks actually contain
    the expected evidence needed to answer the question.

    At least ONE retrieved chunk must contain ALL
    expected keywords.
    """

    if not retrieved_chunks:
        return False

    normalized_keywords = [
        normalize_text(keyword)
        for keyword in expected_keywords
    ]

    for chunk in retrieved_chunks:

        chunk_text = normalize_text(
            chunk.get("text", "")
        )

        # All expected keywords must occur
        # in the same retrieved chunk.
        if all(
            keyword in chunk_text
            for keyword in normalized_keywords
        ):
            return True

    return False


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
        raise ValueError("test_dataset.json contains no test cases.")

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
    # Failed retrieval cases will NOT consume Gemini quota.

    GEMINI_EVALUATION_CASES = 5

    gemini_cases_completed = 0
    gemini_cases_failed = 0

    # ========================================================
    # PROCESS EACH TEST CASE
    # ========================================================

    for index, case in enumerate(dataset, start=1):

        question = case["question"]

        print(f"\n[{index}/{len(dataset)}] Evaluating: {question}")

        # ----------------------------------------------------
        # Expected values
        # ----------------------------------------------------

        expected_source = case.get("expected_source")
        expected_keywords = case.get("expected_answer_keywords", [])

        # ====================================================
        # PART 1 — RETRIEVAL EVALUATION
        # ====================================================

        retrieval_start = time.perf_counter()

        try:
            retrieved = retrieve(question, db, top_k=5)
            usable_chunks = filter_relevant_chunks(retrieved)
        except Exception as e:
            print("  Retrieval ERROR:", str(e))
            retrieved = []
            usable_chunks =[]

        retrieval_latency_ms = (
            time.perf_counter() - retrieval_start
        ) * 1000

        # ====================================================
        # ACTUAL RETRIEVED DOCUMENTS
        # ====================================================

        actual_sources = [
            chunk["document"]
            for chunk in usable_chunks
        ]

        # ====================================================
        # RETRIEVAL ACCURACY
        # ====================================================

        if expected_source is None:

    # Out-of-context question should have no relevant evidence.
            retrieval_hit = len(usable_chunks) == 0

        else:

    # Check whether expected document was retrieved.
            document_retrieved = (
                expected_source in actual_sources
                )

    # Check whether retrieved chunks contain
    # the expected answer evidence.
            evidence_retrieved = retrieval_evidence_is_correct(
             usable_chunks,
                expected_keywords,
         )

    # Retrieval succeeds only when both conditions pass.
            retrieval_hit = (
                 document_retrieved
             and evidence_retrieved
             )

        # ====================================================
        # CITATION ACCURACY
        # ====================================================

        citation_correct = citation_is_correct(
            expected_source,
            actual_sources,
        )

        # ====================================================
        # PRINT RETRIEVAL RESULT
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
            "  Retrieval latency:",
            f"{retrieval_latency_ms:.0f} ms",
        )

        # ----------------------------------------------------
        # Show retrieved documents
        # ----------------------------------------------------

        if actual_sources:

            print("  Retrieved documents:")

            for chunk in retrieved:

                print(
                    f"    - {chunk['document']} "
                    f"(page {chunk['page']}, "
                    f"score={chunk['score']:.4f})"
                )

        else:

            print("  Retrieved documents: NONE")

        # ====================================================
        # PART 2 — GEMINI ANSWER EVALUATION
        # ====================================================

        answer = ""
        grounded = False
        answer_correct = False
        hallucinated = False
        answer_latency_ms = 0.0

        # ----------------------------------------------------
        # Gemini protection
        #
        # Gemini runs ONLY when:
        #
        # 1. We have not exceeded 5 Gemini cases
        # 2. Retrieval passed
        #
        # This prevents wasting API calls on bad retrievals.
        # ----------------------------------------------------

        if gemini_cases_completed < GEMINI_EVALUATION_CASES and retrieval_hit:

            print("  Gemini: RUNNING")

            answer_start = time.perf_counter()

            try:

                result = answer_question(
                    question,
                    db,
                )

                answer_latency_ms = (
                    time.perf_counter() - answer_start
                ) * 1000

                gemini_cases_completed += 1

                # ------------------------------------------------
                # Extract answer
                # ------------------------------------------------

                answer = result.get("answer", "")

                # ------------------------------------------------
                # Extract sources
                # ------------------------------------------------

                sources = result.get("sources", [])

                # ------------------------------------------------
                # Extract grounded flag
                # ------------------------------------------------

                grounded = result.get("grounded", False)

                # ------------------------------------------------
                # Answer correctness
                # ------------------------------------------------

                answer_correct = answer_is_correct(
                    answer,
                    expected_keywords,
                )

                # ------------------------------------------------
                # Hallucination detection
                # ------------------------------------------------

                hallucinated = (
                    expected_source is None and grounded
                ) or (
                    expected_source is not None and not grounded
                )

                # ------------------------------------------------
                # Print answer result
                # ------------------------------------------------

                print(
                    "  Answer:",
                    "PASS" if answer_correct else "FAIL",
                )

                print("  Grounded:", grounded)

                print(
                    "  Answer latency:",
                    f"{answer_latency_ms:.0f} ms",
                )

                # ------------------------------------------------
                # If answer fails, show why
                # ------------------------------------------------

                if not answer_correct:

                    print("  Generated answer:", answer)
                    print(
                        "  Expected keywords:",
                        expected_keywords,
                    )

                # ------------------------------------------------
                # Compare answer sources
                # ------------------------------------------------

                answer_sources = [
                    source["document"]
                    for source in sources
                ]

                print(
                    "  Answer sources:",
                    answer_sources,
                )

            except Exception as e:

                answer_latency_ms = (
                    time.perf_counter() - answer_start
                ) * 1000

                gemini_cases_failed += 1

                print("  Gemini ERROR:", str(e))
                print("  Gemini case marked as failed.")

        else:

            if not retrieval_hit:

                print(
                    "  Gemini: SKIPPED "
                    "(retrieval failed)"
                )

            else:

                print(
                    "  Gemini: SKIPPED "
                    "(evaluation limit reached)"
                )

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
                "expected_source": expected_source,
                "expected_answer_keywords": expected_keywords,
                "actual_answer": answer,
                "actual_sources": actual_sources,
                "retrieval_hit": retrieval_hit,
                "answer_correct": answer_correct,
                "citation_correct": citation_correct,
                "grounded": grounded,
                "hallucinated": hallucinated,
                "retrieval_latency_ms": round(
                    retrieval_latency_ms,
                    1,
                ),
                "answer_latency_ms": round(
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
    )

    # --------------------------------------------------------
    # Citation accuracy
    # --------------------------------------------------------

    citation_accuracy = (
        citation_correct_count / total_cases
    )

    # --------------------------------------------------------
    # Gemini metrics
    # --------------------------------------------------------

    if gemini_cases_completed > 0:

        answer_correctness = (
            answer_correct_count
            / gemini_cases_completed
        )

        hallucination_rate = (
            hallucinated_count
            / gemini_cases_completed
        )

    else:

        answer_correctness = 0.0
        hallucination_rate = 0.0

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
        avg_latency_ms=0.0,
        results=results,
    )

    db.add(evaluation_run)
    db.commit()
    db.refresh(evaluation_run)

    # ========================================================
    # FINAL OUTPUT
    # ========================================================

    print("\n" + "=" * 60)
    print("EVALUATION COMPLETE")
    print("=" * 60)

    print(
        f"Total test cases       : {total_cases}"
    )

    print(
        f"Gemini cases completed : {gemini_cases_completed}"
    )

    print(
        f"Gemini cases failed    : {gemini_cases_failed}"
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

    print("=" * 60)

    return evaluation_run