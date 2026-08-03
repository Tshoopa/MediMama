# backend/query_expansion.py

from backend.semantic_concepts import detect_concepts, get_retrieval_hint


def expand(query: str) -> str:
    """Optionally append a retrieval hint for the top-matched semantic concept.

    Non-critical: on any failure (or no match), returns the original query
    unchanged. This layer must never crash /ask.
    """
    if not query or not query.strip():
        return query

    try:
        concepts = detect_concepts(query)
    except Exception as e:
        print("[query_expansion] detect_concepts failed; using original query:", repr(e))
        return query

    if not concepts:
        return query

    try:
        top_concept, score = concepts[0]
        hint = get_retrieval_hint(top_concept)
        if hint:
            print(f"[query_expansion] '{top_concept}' (sim={score}) -> +'{hint}'")
            return f"{query} {hint}"
        return query
    except Exception as e:
        print("[query_expansion] formatting failed; using original query:", repr(e))
        return query