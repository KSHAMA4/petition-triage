import chromadb
from sentence_transformers import SentenceTransformer

_model = None
_col = None


def _load():
    global _model, _col
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        _col = chromadb.PersistentClient(path="index_store").get_collection("regulations")
    return _model, _col


def search_corpus(query, k=5, doc=None):
    model, col = _load()
    kw = {"where": {"doc": doc}} if doc else {}
    res = col.query(query_embeddings=model.encode([query]).tolist(), n_results=k, **kw)
    return [{"doc": m["doc"], "clause": m["clause"], "page": m["page"], "text": d}
            for d, m in zip(res["documents"][0], res["metadatas"][0])]

def get_clause(doc, clause):
    _, col = _load()
    res = col.get(where={"$and": [{"doc": doc}, {"clause": str(clause)}]})
    return [{"doc": m["doc"], "clause": m["clause"], "page": m["page"], "text": d}
            for d, m in zip(res["documents"], res["metadatas"])]


def get_petition_fields(petition):
    return petition