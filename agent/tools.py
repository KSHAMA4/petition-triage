import chromadb
from sentence_transformers import SentenceTransformer
from agent.resilience import get_cached, set_cached

_model = None
_col = None


def _load():
    global _model, _col
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _col = chromadb.PersistentClient(path="index_store").get_collection("regulations")
    return _model, _col


def search_corpus(query, k=5, doc=None):
    cache_key = f"{doc or 'all'}:{k}:{query}"
    cached = get_cached("search", cache_key)
    if cached is not None:
        return cached

    model, col = _load()
    kw = {"where": {"doc": doc}} if doc else {}
    res = col.query(query_embeddings=model.encode([query]).tolist(), n_results=k, **kw)
    result = [{"doc": m["doc"], "clause": m["clause"], "page": m["page"], "text": d}
              for d, m in zip(res["documents"][0], res["metadatas"][0])]
    set_cached("search", cache_key, result, ttl_seconds=3600)
    return result


def get_clause(doc, clause):
    cache_key = f"{doc or 'all'}:{clause}"
    cached = get_cached("clause", cache_key)
    if cached is not None:
        return cached

    _, col = _load()
    res = col.get(where={"$and": [{"doc": doc}, {"clause": str(clause)}]})
    result = [{"doc": m["doc"], "clause": m["clause"], "page": m["page"], "text": d}
              for d, m in zip(res["documents"], res["metadatas"])]
    set_cached("clause", cache_key, result, ttl_seconds=3600)
    return result


def get_petition_fields(petition):
    return petition
