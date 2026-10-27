import sys
import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")
col = chromadb.PersistentClient(path="index_store").get_collection("regulations")
q = " ".join(sys.argv[1:])
res = col.query(query_embeddings=model.encode([q]).tolist(), n_results=5)
for d, m in zip(res["documents"][0], res["metadatas"][0]):
    print(f"\n[{m['doc']} | {m['chapter']} | clause {m['clause']} | page {m['page']}]\n{d[:400]}")