import re, json, time, hashlib, pathlib
import pymupdf
import chromadb
from sentence_transformers import SentenceTransformer

CORPUS_DIR = pathlib.Path("corpus")
INDEX_DIR = "index_store"
MAX_CHARS = 1200
CHAPTER_RE = re.compile(r"^\s*chapter\s+[\w\.\-]+", re.I)
CLAUSE_RE = re.compile(r"^\s*(\d+(?:\.\d+){0,3})[\.\)]?\s+\S")
SUB_RE = re.compile(r"(?=(?<!\d)\d{1,2}\.\d{1,2}\.\s+[A-Z])")
LABEL_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\.\s")


def chunk_pdf(path):
    doc = pymupdf.open(path)
    state = {"chapter": "Preamble", "clause": "0"}
    buf, chunks = [], []

    def flush(page):
        text = " ".join(buf).strip()
        buf.clear()
        for piece in SUB_RE.split(text):
            piece = piece.strip()
            if not piece:
                continue
            m = LABEL_RE.match(piece)
            if m:
                state["clause"] = m.group(1)
            if len(piece) > 40:
                chunks.append({"text": piece, "doc": path.name,
                               "chapter": state["chapter"],
                               "clause": state["clause"], "page": page})

    for pno, page in enumerate(doc, start=1):
        for line in page.get_text().splitlines():
            line = line.strip()
            if not line:
                continue
            if CHAPTER_RE.match(line):
                flush(pno)
                state["chapter"] = line[:80]
            m = CLAUSE_RE.match(line)
            if m:
                flush(pno)
                state["clause"] = m.group(1)
            buf.append(line)
            if sum(len(x) for x in buf) > MAX_CHARS:
                flush(pno)
    flush(len(doc))
    return chunks


def main():
    model = SentenceTransformer("all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=INDEX_DIR)
    col = client.get_or_create_collection("regulations")
    total, docs = 0, []
    for pdf in sorted(CORPUS_DIR.glob("*.pdf")):
        chunks = chunk_pdf(pdf)
        try:
            col.delete(where={"doc": pdf.name})
        except Exception:
            pass
        ids = [hashlib.sha1(f"{c['doc']}|{i}|{c['page']}|{c['text']}".encode()).hexdigest()
               for i, c in enumerate(chunks)]
        embs = model.encode([c["text"] for c in chunks]).tolist()
        metas = [{k: c[k] for k in ("doc", "chapter", "clause", "page")} for c in chunks]
        col.upsert(ids=ids, embeddings=embs,
                   documents=[c["text"] for c in chunks], metadatas=metas)
        total += len(chunks)
        docs.append(pdf.name)
        print(f"{pdf.name}: {len(chunks)} chunks")
    manifest = {"built_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "documents": docs,
                "chunks": total, "embedding_model": "all-MiniLM-L6-v2"}
    pathlib.Path(INDEX_DIR).mkdir(exist_ok=True)
    pathlib.Path(INDEX_DIR, "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(manifest)


if __name__ == "__main__":
    main()