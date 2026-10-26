from backend.app.services.search import search_service
from backend.app.services.qa import qa_service
from backend.app.services.embeddings import embedding_service

def test_embeddings_generation():
    vec1 = embedding_service.embed_text("Cloud database cluster")
    vec2 = embedding_service.embed_text("Cloud database cluster")
    vec3 = embedding_service.embed_text("Vegetable garden organic soil")
    
    assert len(vec1) == 384
    # Determinism
    assert vec1 == vec2
    
    sim_similar = embedding_service.cosine_similarity(vec1, vec2)
    sim_diff = embedding_service.cosine_similarity(vec1, vec3)
    assert sim_similar > 0.99
    assert sim_similar > sim_diff

def test_search_modes(db_session):
    # Lexical, semantic, and hybrid search
    lex_res = search_service.search("Apex Cloud Infrastructure", db=db_session, mode="lexical", top_k=3)
    assert lex_res["retrieval_mode"] == "lexical"
    assert "ApexCloud" in str(lex_res["results"]) or len(lex_res["results"]) > 0

    sem_res = search_service.search("high performance cloud compute", db=db_session, mode="semantic", top_k=3)
    assert sem_res["retrieval_mode"] == "semantic"
    assert len(sem_res["results"]) > 0

    hyb_res = search_service.search("Kubernetes hosting clusters", db=db_session, mode="hybrid", top_k=3)
    assert hyb_res["retrieval_mode"] == "hybrid"
    assert len(hyb_res["results"]) > 0
    # Check score inspection
    first_hit = hyb_res["results"][0]
    assert "score" in first_hit
    assert "page_number" in first_hit
    assert "snippet" in first_hit

def test_qa_service_with_citations_and_insufficiency(db_session):
    # Query with known facts
    qa_found = qa_service.answer_question("What is the invoice number for Apex Cloud?", db=db_session)
    assert qa_found["evidence_status"] == "sufficient"
    assert len(qa_found["citations"]) > 0
    assert "INV-2026-001" in qa_found["answer"] or "Apex" in qa_found["answer"]

    # Query with impossible facts -> insufficiency detection
    qa_unknown = qa_service.answer_question("xyzquantum9999nonexistent spacecraft warp drive coordinates", db=db_session)
    assert qa_unknown["evidence_status"] == "insufficient"
    assert "insufficient" in qa_unknown["answer"].lower()
