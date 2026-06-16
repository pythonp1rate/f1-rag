import os
import uuid
import json
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

CHUNK_SIZE  = 350
OVERLAP     = 50
DATA_DIR    = "data"
COLLECTION  = "f1_docs"
CHUNKS_FILE = "chunks_store.json"


def chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + CHUNK_SIZE])
        if len(chunk.strip()) > 80:
            chunks.append(chunk)
        i += CHUNK_SIZE - OVERLAP
    return chunks


def stem_to_source(stem: str) -> tuple[str, str]:
    """
    Returns (source_name, source_type).
    Fandom files are prefixed with 'fandom_' — strip the prefix for the
    display name but record the type so we can filter by source later.
    """
    if stem.startswith("fandom_"):
        name = stem[len("fandom_"):].replace("_", " ")
        return name, "fandom"
    return stem.replace("_", " "), "wikipedia"


def build_index():
    emb_fn = OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="nomic-embed-text"
    )

    client = chromadb.PersistentClient(path=".chroma")

    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass

    collection = client.create_collection(COLLECTION, embedding_function=emb_fn)

    all_docs, all_ids, all_metas = [], [], []

    txt_files = sorted(Path(DATA_DIR).glob("*.txt"))
    for fpath in txt_files:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        source_name, source_type = stem_to_source(fpath.stem)
        for chunk in chunk_text(text):
            all_docs.append(chunk)
            all_ids.append(str(uuid.uuid4()))
            all_metas.append({"source": source_name, "source_type": source_type})

    wiki_files   = sum(1 for f in txt_files if not f.stem.startswith("fandom_"))
    fandom_files = sum(1 for f in txt_files if f.stem.startswith("fandom_"))
    print(f"ingesting {len(all_docs)} chunks from "
          f"{wiki_files} Wikipedia + {fandom_files} Fandom files...")

    for i in range(0, len(all_docs), 50):
        collection.add(
            documents=all_docs[i:i+50],
            ids=all_ids[i:i+50],
            metadatas=all_metas[i:i+50]
        )
        print(f"  {min(i+50, len(all_docs))}/{len(all_docs)}")

    with open(CHUNKS_FILE, "w") as f:
        json.dump({"ids": all_ids, "docs": all_docs, "metas": all_metas}, f)

    print(f"done. index saved to .chroma/ and {CHUNKS_FILE}")


if __name__ == "__main__":
    build_index()
