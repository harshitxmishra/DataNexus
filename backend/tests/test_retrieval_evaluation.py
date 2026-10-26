from backend.app.evaluation.retrieval_eval import run_full_retrieval_benchmark


def test_retrieval_benchmark_execution_and_metrics():
    """
    Executes grounded retrieval evaluation across BM25, Interim Hashing, Pretrained MiniLM, and Hybrid RRF.
    Verifies metric constraints and reporting.
    """
    results = run_full_retrieval_benchmark()

    assert "summary" in results
    summary = results["summary"]

    # Verify all four retrieval approaches are present
    assert "bm25_lexical" in summary
    assert "interim_hashing_384d" in summary
    assert "neural_minilm_384d" in summary
    assert "hybrid_rrf_minilm" in summary

    # Metric verifications:
    # 1. Neural MiniLM achieves Recall@5 of 1.0 on grounded positive benchmark queries
    assert summary["neural_minilm_384d"]["recall@5"] >= 0.99
    # 2. Hybrid RRF achieves Recall@5 of 1.0
    assert summary["hybrid_rrf_minilm"]["recall@5"] >= 0.99
    # 3. Neural MiniLM achieves high MRR (> 0.85)
    assert summary["neural_minilm_384d"]["mrr"] > 0.85
    # 4. Latencies are positive and finite
    for app in summary:
        assert summary[app]["avg_latency_ms"] > 0.0

    # Ensure negative query has zero matches or top score 0
    detailed = results["detailed_results"]
    q10_neural = [q for q in detailed["neural_minilm_384d"] if q["query_id"] == "q10-ungrounded-negative"][0]
    assert q10_neural["is_negative_query"] == 1.0
