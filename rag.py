import json
import os
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
from rank_bm25 import BM25Okapi
import ollama

COLLECTION  = "f1_docs"
_BASE       = Path(__file__).parent
CHUNKS_FILE = str(_BASE / "chunks_store.json")
POOL_SIZE   = 20
TOP_K       = 6

# -- ChromaDB --
_emb_fn = OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text"
)
_chroma     = chromadb.PersistentClient(path=str(_BASE / ".chroma"))
_collection = _chroma.get_collection(COLLECTION, embedding_function=_emb_fn)

# -- BM25 --
with open(CHUNKS_FILE) as f:
    _store = json.load(f)

_all_ids   = _store["ids"]
_all_docs  = _store["docs"]
_all_metas = _store["metas"]

_bm25 = BM25Okapi([doc.lower().split() for doc in _all_docs])


# ---- retrievers ----

def dense_retrieve(query: str, k: int = POOL_SIZE) -> list[dict]:
    results = _collection.query(query_texts=[query], n_results=k)
    return [
        {"id": id_, "text": doc, "source": meta["source"], "distance": dist}
        for id_, doc, meta, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )
    ]


def sparse_retrieve(query: str, k: int = POOL_SIZE) -> list[dict]:
    scores = _bm25.get_scores(query.lower().split())
    top_i  = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
    return [
        {
            "id": _all_ids[i],
            "text": _all_docs[i],
            "source": _all_metas[i]["source"],
            "bm25_score": float(scores[i])
        }
        for i in top_i
    ]


def reciprocal_rank_fusion(dense: list[dict], sparse: list[dict], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    for rank, chunk in enumerate(dense):
        cid = chunk["id"]
        scores[cid]    = scores.get(cid, 0) + 1 / (k + rank + 1)
        chunk_map[cid] = chunk

    for rank, chunk in enumerate(sparse):
        cid = chunk["id"]
        scores[cid]    = scores.get(cid, 0) + 1 / (k + rank + 1)
        chunk_map[cid] = chunk

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{**chunk_map[cid], "rrf_score": score} for cid, score in ranked]


# ---- generation ----

SYSTEM_PROMPT = """You are an expert Formula 1 analyst. Answer questions using 
ONLY the context provided below. If the answer is not in the context, say so.
Be specific and factual."""


def generate(query: str, chunks: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[{c['source']}]\n{c['text']}" for c in chunks
    )
    resp = ollama.chat(
        model="llama3.2",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context:\n{context}\n\nQuestion: {query}"}
        ]
    )
    return resp.message.content


# ---- corpus info ----

def get_corpus_stats() -> dict:
    n_chunks = len(_all_docs)
    n_articles = len(set(m["source"] for m in _all_metas))
    return {"chunks": n_chunks, "articles": n_articles}


# ---- public API ----

def ask_hybrid(query: str, top_k: int = TOP_K) -> dict:
    dense  = dense_retrieve(query, k=POOL_SIZE)
    sparse = sparse_retrieve(query, k=POOL_SIZE)
    fused  = reciprocal_rank_fusion(dense, sparse)[:top_k]
    return {"answer": generate(query, fused), "sources": fused, "mode": "hybrid"}


def ask_naive(query: str, top_k: int = TOP_K) -> dict:
    chunks = dense_retrieve(query, k=top_k)
    return {"answer": generate(query, chunks), "sources": chunks, "mode": "naive"}