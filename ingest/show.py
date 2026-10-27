import sys
import chromadb

col = chromadb.PersistentClient(path="index_store").get_collection("regulations")
doc_name, clause = sys.argv[1], sys.argv[2]
res = col.get(where={"$and": [{"doc": doc_name}, {"clause": clause}]})
for d, m in zip(res["documents"], res["metadatas"]):
    print(f"\n[{m['doc']} | clause {m['clause']} | page {m['page']}]\n{d}\n")