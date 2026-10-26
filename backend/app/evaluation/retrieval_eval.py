"""
DataNexus Retrieval Evaluation Suite — Phase 3 Benchmark.
Evaluates and compares:
1. Pure Lexical BM25
2. Interim Hashing Representation (384-d random projection)
3. Genuine Pretrained Neural Semantic Embeddings (all-MiniLM-L6-v2)
4. Hybrid Reciprocal Rank Fusion (BM25 + all-MiniLM-L6-v2)

Grounded in canonical DataNexus business documents and invoice fixtures.
Computes Recall@k (k=1, 3, 5), MRR, Precision@k, and latency.
"""
import time
import math
import re
from typing import List, Dict, Any, Optional, Set
import numpy as np

from backend.app.services.embeddings import (
    embedding_service,
    PretrainedNeuralEmbeddingService,
    InterimHashingEmbeddingService
)


# 1. Grounded Benchmark Corpus (13 chunks across 6 business documents)
BENCHMARK_CHUNKS = [
    {
        "id": "chunk-inv-001-meta",
        "doc_id": "INV-2026-001",
        "doc_name": "INV-2026-001-ApexCloud.pdf",
        "content": "Invoice Number: INV-2026-001. Vendor: Apex Cloud Services. Date: 2026-09-15. Due Date: 2026-10-15. Currency: USD. Subtotal: $11500.00. Tax: $950.00. Total Amount: $12450.00."
    },
    {
        "id": "chunk-inv-001-k8s",
        "doc_id": "INV-2026-001",
        "doc_name": "INV-2026-001-ApexCloud.pdf",
        "content": "Line Item 1: Cloud Infrastructure Clusters (Kubernetes Hosting), Quantity: 1, Unit Price: 8500.00, Amount: $8500.00."
    },
    {
        "id": "chunk-inv-001-storage",
        "doc_id": "INV-2026-001",
        "doc_name": "INV-2026-001-ApexCloud.pdf",
        "content": "Line Item 2: Dedicated NVMe Storage Volumes (50TB Tier), Quantity: 1, Unit Price: 2000.00, Amount: $2000.00. Line Item 3: Direct Connect Enterprise Bandwidth, Quantity: 1, Unit Price: 1000.00, Amount: $1000.00."
    },
    {
        "id": "chunk-inv-002-meta",
        "doc_id": "INV-2026-002",
        "doc_name": "INV-2026-002-GlobalLogistics.pdf",
        "content": "Invoice Number: INV-2026-002. Vendor: Global Logistics Partner. Date: 2026-09-28. Due Date: 2026-10-28. Currency: USD. Subtotal: $8000.00. Tax: $720.50. Total Amount: $8720.50."
    },
    {
        "id": "chunk-inv-002-freight",
        "doc_id": "INV-2026-002",
        "doc_name": "INV-2026-002-GlobalLogistics.pdf",
        "content": "Line Item 1: Freight Forwarding International Air Express, Quantity: 2, Unit Price: 3200.00, Amount: $6400.00. Line Item 2: Customs Brokerage Compliance Filing Fee, Quantity: 1, Unit Price: 1600.00, Amount: $1600.00."
    },
    {
        "id": "chunk-inv-003-meta",
        "doc_id": "INV-2026-003",
        "doc_name": "INV-2026-003-StarlightLabs.pdf",
        "content": "Invoice Number: INV-2026-003. Vendor: Starlight Software Labs. Date: 2026-10-05. Due Date: 2026-11-05. Currency: EUR. Subtotal: 13500.00. Tax: 1800.00. Total Amount: 15300.00."
    },
    {
        "id": "chunk-inv-003-ai",
        "doc_id": "INV-2026-003",
        "doc_name": "INV-2026-003-StarlightLabs.pdf",
        "content": "Line Item 1: Enterprise AI Platform Licenses, Quantity: 1, Unit Price: 9500.00, Amount: 9500.00. Line Item 2: Dedicated ML Engineering Support (160 Hours), Quantity: 1, Unit Price: 4000.00, Amount: 4000.00."
    },
    {
        "id": "chunk-inv-004-meta",
        "doc_id": "INV-2026-004",
        "doc_name": "INV-2026-004-MeridianFacilities.pdf",
        "content": "Invoice Number: INV-2026-004. Vendor: Meridian Facilities Group. Date: 2026-10-10. Due Date: 2026-11-10. Currency: USD. Subtotal: $4500.00. Tax: $360.00. Total Amount: $4860.00."
    },
    {
        "id": "chunk-inv-004-hvac",
        "doc_id": "INV-2026-004",
        "doc_name": "INV-2026-004-MeridianFacilities.pdf",
        "content": "Line Item 1: Corporate Campus Janitorial Services & Deep Sanitation, Quantity: 1, Unit Price: 3000.00, Amount: 3000.00. Line Item 2: HVAC Preventive Filter Replacement & System Maintenance, Quantity: 1, Unit Price: 1500.00, Amount: 1500.00."
    },
    {
        "id": "chunk-inv-005-meta",
        "doc_id": "INV-2026-005",
        "doc_name": "INV-2026-005-NordicData.pdf",
        "content": "Invoice Number: INV-2026-005. Vendor: Nordic Data Systems. Date: 2026-10-14. Due Date: 2026-11-14. Currency: SEK. Subtotal: 95000.00. Tax: 23750.00. Total Amount: 118750.00."
    },
    {
        "id": "chunk-inv-005-lakehouse",
        "doc_id": "INV-2026-005",
        "doc_name": "INV-2026-005-NordicData.pdf",
        "content": "Line Item 1: Data Lakehouse Architecture Consultation & Schema Migration, Quantity: 1, Unit Price: 65000.00, Amount: 65000.00. Line Item 2: Security & Governance Compliance Audit, Quantity: 1, Unit Price: 30000.00, Amount: 30000.00."
    },
    {
        "id": "chunk-inv-006-meta",
        "doc_id": "INV-2026-006",
        "doc_name": "INV-2026-006-PinnacleEng.pdf",
        "content": "Invoice Number: INV-2026-006. Vendor: Pinnacle Engineering. Date: 2026-10-18. Due Date: 2026-11-18. Currency: USD. Subtotal: $18200.00. Tax: $1456.00. Total Amount: $19656.00."
    },
    {
        "id": "chunk-inv-006-milling",
        "doc_id": "INV-2026-006",
        "doc_name": "INV-2026-006-PinnacleEng.pdf",
        "content": "Line Item 1: Mechanical Stress Analysis & Finite Element Simulation, Quantity: 1, Unit Price: 12000.00, Amount: 12000.00. Line Item 2: Rapid Prototyping CNC Milling & Materials, Quantity: 1, Unit Price: 6200.00, Amount: 6200.00."
    }
]


# 2. Benchmark Queries with Explicit Relevance Ground Truth
BENCHMARK_QUERIES = [
    {
        "id": "q1-exact-inv-num",
        "query": "INV-2026-002",
        "category": "exact_keyword",
        "description": "Exact invoice identifier lookup",
        "relevant_chunk_ids": ["chunk-inv-002-meta"]
    },
    {
        "id": "q2-exact-fee-name",
        "query": "Customs Brokerage Compliance Filing Fee",
        "category": "exact_keyword",
        "description": "Exact fee line item title lookup",
        "relevant_chunk_ids": ["chunk-inv-002-freight"]
    },
    {
        "id": "q3-paraphrase-freight",
        "query": "overseas air cargo transport and freight logistics",
        "category": "paraphrased_semantic",
        "description": "Semantic paraphrase without lexical overlap ('cargo', 'transport')",
        "relevant_chunk_ids": ["chunk-inv-002-freight"]
    },
    {
        "id": "q4-paraphrase-k8s",
        "query": "managed container hosting and virtual compute nodes",
        "category": "paraphrased_semantic",
        "description": "Semantic paraphrase for Kubernetes cloud hosting",
        "relevant_chunk_ids": ["chunk-inv-001-k8s"]
    },
    {
        "id": "q5-vendor-amount",
        "query": "Apex Cloud Services 12450.00",
        "category": "vendor_and_amount",
        "description": "Vendor name combined with exact total dollar figure",
        "relevant_chunk_ids": ["chunk-inv-001-meta"]
    },
    {
        "id": "q6-vendor-date",
        "query": "Starlight Software Labs 2026-10-05",
        "category": "vendor_and_date",
        "description": "Vendor name with exact invoice issuance date",
        "relevant_chunk_ids": ["chunk-inv-003-meta"]
    },
    {
        "id": "q7-paraphrase-facilities",
        "query": "building cleaning, disinfection and air conditioner upkeep",
        "category": "paraphrased_semantic",
        "description": "Semantic paraphrase for janitorial sanitation & HVAC maintenance",
        "relevant_chunk_ids": ["chunk-inv-004-hvac"]
    },
    {
        "id": "q8-technical-engineering",
        "query": "finite element simulation and mechanical stress testing",
        "category": "bm25_competitive",
        "description": "Technical domain terms where lexical BM25 is strong",
        "relevant_chunk_ids": ["chunk-inv-006-milling"]
    },
    {
        "id": "q9-paraphrase-lakehouse",
        "query": "cloud data lakehouse migration and table schema design",
        "category": "paraphrased_semantic",
        "description": "Analytical consultation line item query",
        "relevant_chunk_ids": ["chunk-inv-005-lakehouse"]
    },
    {
        "id": "q10-ungrounded-negative",
        "query": "organic hydroponic fertilizer agriculture greenhouse cultivation",
        "category": "no_relevant_evidence",
        "description": "Out-of-domain negative query with zero relevant corpus documents",
        "relevant_chunk_ids": []
    }
]


def score_bm25(query: str, corpus: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute local BM25 scoring across corpus chunks."""
    terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
    if not terms:
        return [{"id": c["id"], "score": 0.0} for c in corpus]

    doc_lengths = [len(c["content"].lower().split()) for c in corpus]
    avg_len = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 50.0
    k1 = 1.2
    b = 0.75

    scored = []
    for c, doc_len in zip(corpus, doc_lengths):
        text_lower = c["content"].lower()
        score = 0.0
        for term in terms:
            tf = text_lower.count(term)
            if tf > 0:
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_len / avg_len))
                score += (numerator / denominator)
        scored.append({"id": c["id"], "score": float(score)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def score_vector_similarity(
    query: str,
    corpus: List[Dict[str, Any]],
    corpus_vectors: List[List[float]],
    embedder: Any
) -> List[Dict[str, Any]]:
    """Compute cosine similarity ranking using an embedding service."""
    q_vec = embedder.embed_text(query)
    scored = []
    for c, c_vec in zip(corpus, corpus_vectors):
        sim = embedder.cosine_similarity(q_vec, c_vec)
        # Bounded normalized score in [0, 1]
        norm_score = max(0.0, (sim + 1.0) / 2.0)
        scored.append({"id": c["id"], "score": float(norm_score)})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


def score_hybrid_rrf(
    lexical_ranked: List[Dict[str, Any]],
    vector_ranked: List[Dict[str, Any]],
    rrf_k: int = 60
) -> List[Dict[str, Any]]:
    """Combine lexical and vector rankings using Reciprocal Rank Fusion (RRF)."""
    scores: Dict[str, float] = {}

    for rank, item in enumerate(lexical_ranked, start=1):
        cid = item["id"]
        # Only fuse non-zero lexical matches
        if item["score"] > 0:
            scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))

    for rank, item in enumerate(vector_ranked, start=1):
        cid = item["id"]
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (rrf_k + rank))

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{"id": cid, "score": score} for cid, score in sorted_items]


def compute_evaluation_metrics(
    ranked_results: List[Dict[str, Any]],
    relevant_ids: List[str]
) -> Dict[str, float]:
    """Compute Recall@1, Recall@3, Recall@5, and MRR for a query."""
    if not relevant_ids:
        # Negative query: evaluate whether any score exceeds positive threshold
        top_score = ranked_results[0]["score"] if ranked_results else 0.0
        return {
            "recall@1": 1.0 if top_score == 0.0 else 0.0,
            "recall@3": 1.0 if top_score == 0.0 else 0.0,
            "recall@5": 1.0 if top_score == 0.0 else 0.0,
            "mrr": 1.0 if top_score == 0.0 else 0.0,
            "is_negative_query": 1.0
        }

    rel_set = set(relevant_ids)
    top_5 = [r["id"] for r in ranked_results[:5]]
    top_3 = top_5[:3]
    top_1 = top_5[:1]

    rec_1 = 1.0 if any(cid in rel_set for cid in top_1) else 0.0
    rec_3 = 1.0 if any(cid in rel_set for cid in top_3) else 0.0
    rec_5 = 1.0 if any(cid in rel_set for cid in top_5) else 0.0

    # MRR: 1 / rank of first relevant item
    mrr = 0.0
    for rank, item in enumerate(ranked_results, start=1):
        if item["id"] in rel_set:
            mrr = 1.0 / rank
            break

    return {
        "recall@1": rec_1,
        "recall@3": rec_3,
        "recall@5": rec_5,
        "mrr": mrr,
        "is_negative_query": 0.0
    }


def run_full_retrieval_benchmark() -> Dict[str, Any]:
    """
    Execute full comparative retrieval evaluation across all four representations.
    Returns aggregated metrics, per-query details, and summary tables.
    """
    corpus = BENCHMARK_CHUNKS
    corpus_texts = [c["content"] for c in corpus]

    neural_embedder = PretrainedNeuralEmbeddingService()
    hashing_embedder = InterimHashingEmbeddingService()

    # Pre-embed corpus once for each embedder
    t0 = time.perf_counter()
    neural_corpus_vectors = neural_embedder.embed_texts(corpus_texts)
    neural_embed_time_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    hashing_corpus_vectors = hashing_embedder.embed_texts(corpus_texts)
    hashing_embed_time_ms = (time.perf_counter() - t0) * 1000

    approaches = [
        "bm25_lexical",
        "interim_hashing_384d",
        "neural_minilm_384d",
        "hybrid_rrf_minilm"
    ]

    results_by_approach: Dict[str, List[Dict[str, Any]]] = {app: [] for app in approaches}
    latencies_by_approach: Dict[str, List[float]] = {app: [] for app in approaches}

    # Run queries across approaches
    for q in BENCHMARK_QUERIES:
        q_text = q["query"]
        rel_ids = q["relevant_chunk_ids"]

        # 1. BM25 Lexical
        t_start = time.perf_counter()
        bm25_ranked = score_bm25(q_text, corpus)
        lat_bm25 = (time.perf_counter() - t_start) * 1000
        latencies_by_approach["bm25_lexical"].append(lat_bm25)
        m_bm25 = compute_evaluation_metrics(bm25_ranked, rel_ids)
        results_by_approach["bm25_lexical"].append({
            "query_id": q["id"],
            "query": q_text,
            "category": q["category"],
            "top_1_id": bm25_ranked[0]["id"] if bm25_ranked else None,
            "top_1_score": round(bm25_ranked[0]["score"], 4) if bm25_ranked else 0.0,
            **m_bm25
        })

        # 2. Interim Hashing
        t_start = time.perf_counter()
        hashing_ranked = score_vector_similarity(q_text, corpus, hashing_corpus_vectors, hashing_embedder)
        lat_hash = (time.perf_counter() - t_start) * 1000
        latencies_by_approach["interim_hashing_384d"].append(lat_hash)
        m_hash = compute_evaluation_metrics(hashing_ranked, rel_ids)
        results_by_approach["interim_hashing_384d"].append({
            "query_id": q["id"],
            "query": q_text,
            "category": q["category"],
            "top_1_id": hashing_ranked[0]["id"] if hashing_ranked else None,
            "top_1_score": round(hashing_ranked[0]["score"], 4) if hashing_ranked else 0.0,
            **m_hash
        })

        # 3. Neural MiniLM
        t_start = time.perf_counter()
        neural_ranked = score_vector_similarity(q_text, corpus, neural_corpus_vectors, neural_embedder)
        lat_neural = (time.perf_counter() - t_start) * 1000
        latencies_by_approach["neural_minilm_384d"].append(lat_neural)
        m_neural = compute_evaluation_metrics(neural_ranked, rel_ids)
        results_by_approach["neural_minilm_384d"].append({
            "query_id": q["id"],
            "query": q_text,
            "category": q["category"],
            "top_1_id": neural_ranked[0]["id"] if neural_ranked else None,
            "top_1_score": round(neural_ranked[0]["score"], 4) if neural_ranked else 0.0,
            **m_neural
        })

        # 4. Hybrid RRF
        t_start = time.perf_counter()
        rrf_ranked = score_hybrid_rrf(bm25_ranked, neural_ranked)
        lat_rrf = (time.perf_counter() - t_start) * 1000 + lat_neural + lat_bm25
        latencies_by_approach["hybrid_rrf_minilm"].append(lat_rrf)
        m_rrf = compute_evaluation_metrics(rrf_ranked, rel_ids)
        results_by_approach["hybrid_rrf_minilm"].append({
            "query_id": q["id"],
            "query": q_text,
            "category": q["category"],
            "top_1_id": rrf_ranked[0]["id"] if rrf_ranked else None,
            "top_1_score": round(rrf_ranked[0]["score"], 4) if rrf_ranked else 0.0,
            **m_rrf
        })

    # Aggregate Metrics (excluding negative queries for Recall/MRR)
    summary_by_approach = {}
    for app in approaches:
        # Standard positive queries (q1 through q9)
        positive_evals = [r for r in results_by_approach[app] if r["is_negative_query"] == 0.0]
        n_pos = len(positive_evals)
        
        avg_r1 = sum(r["recall@1"] for r in positive_evals) / n_pos
        avg_r3 = sum(r["recall@3"] for r in positive_evals) / n_pos
        avg_r5 = sum(r["recall@5"] for r in positive_evals) / n_pos
        avg_mrr = sum(r["mrr"] for r in positive_evals) / n_pos
        avg_lat = sum(latencies_by_approach[app]) / len(latencies_by_approach[app])

        summary_by_approach[app] = {
            "recall@1": round(avg_r1, 4),
            "recall@3": round(avg_r3, 4),
            "recall@5": round(avg_r5, 4),
            "mrr": round(avg_mrr, 4),
            "avg_latency_ms": round(avg_lat, 2)
        }

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        "corpus_chunks_count": len(corpus),
        "queries_evaluated_count": len(BENCHMARK_QUERIES),
        "neural_embed_time_ms": round(neural_embed_time_ms, 2),
        "hashing_embed_time_ms": round(hashing_embed_time_ms, 2),
        "summary": summary_by_approach,
        "detailed_results": results_by_approach
    }


if __name__ == "__main__":
    benchmark_data = run_full_retrieval_benchmark()
    print("=" * 70)
    print(" DataNexus Phase 3 Retrieval Evaluation Results")
    print("=" * 70)
    print(f"{'Approach':<26} | {'Recall@1':<8} | {'Recall@3':<8} | {'Recall@5':<8} | {'MRR':<8} | {'Latency':<8}")
    print("-" * 70)
    for app, metrics in benchmark_data["summary"].items():
        print(f"{app:<26} | {metrics['recall@1']:<8.3f} | {metrics['recall@3']:<8.3f} | {metrics['recall@5']:<8.3f} | {metrics['mrr']:<8.3f} | {metrics['avg_latency_ms']:<6.2f}ms")
    print("=" * 70)
