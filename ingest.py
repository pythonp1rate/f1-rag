import os
import uuid
import json
import argparse
from pathlib import Path
import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

CHUNK_SIZE  = 350
OVERLAP     = 50
DATA_DIR    = "data"
COLLECTION  = "f1_docs"
CHUNKS_FILE = "chunks_store.json"


def chunk_text(text: str, chunk_size=CHUNK_SIZE, overlap=OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + chunk_size])
        if len(chunk.strip()) > 80:
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def stem_to_source(stem: str) -> tuple[str, str]:
    """
    Returns (source_name, source_type).
    Fandom files are prefixed with 'fandom_', ergast files with 'ergast_'.
    Strip the prefix for the display name but keep the type in metadata.
    """
    if stem.startswith("fandom_"):
        name = stem[len("fandom_"):].replace("_", " ")
        return name, "fandom"
    if stem.startswith("jolpica_"):
        name = stem[len("jolpica_"):].replace("_", " ")
        return name, "jolpica"
    return stem.replace("_", " "), "wikipedia"


def build_index(chunk_size=CHUNK_SIZE, overlap=OVERLAP, collection=COLLECTION, chunks_file=CHUNKS_FILE):
    emb_fn = OllamaEmbeddingFunction(
        url="http://localhost:11434/api/embeddings",
        model_name="nomic-embed-text"
    )

    client = chromadb.PersistentClient(path=".chroma")

    try:
        client.delete_collection(collection)
    except Exception:
        pass

    coll = client.create_collection(collection, embedding_function=emb_fn)

    all_docs, all_ids, all_metas = [], [], []

    txt_files = sorted(Path(DATA_DIR).glob("*.txt"))
    for fpath in txt_files:
        text = fpath.read_text(encoding="utf-8", errors="ignore")
        source_name, source_type = stem_to_source(fpath.stem)
        for chunk in chunk_text(text, chunk_size, overlap):
            all_docs.append(chunk)
            all_ids.append(str(uuid.uuid4()))
            all_metas.append({"source": source_name, "source_type": source_type})

    wiki_files   = sum(1 for f in txt_files if not f.stem.startswith("fandom_") and not f.stem.startswith("jolpica_"))
    fandom_files = sum(1 for f in txt_files if f.stem.startswith("fandom_"))
    jolpica_files = sum(1 for f in txt_files if f.stem.startswith("jolpica_"))
    print(f"ingesting {len(all_docs)} chunks (size={chunk_size}) from "
          f"{wiki_files} Wikipedia + {fandom_files} Fandom + {jolpica_files} Jolpica files...")

    for i in range(0, len(all_docs), 50):
        coll.add(
            documents=all_docs[i:i+50],
            ids=all_ids[i:i+50],
            metadatas=all_metas[i:i+50]
        )
        print(f"  {min(i+50, len(all_docs))}/{len(all_docs)}")

    with open(chunks_file, "w") as f:
        json.dump({"ids": all_ids, "docs": all_docs, "metas": all_metas}, f)

    print(f"done. index saved to .chroma/{collection} and {chunks_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--overlap",    type=int, default=OVERLAP)
    parser.add_argument("--collection", type=str, default=COLLECTION)
    parser.add_argument("--chunks-file",type=str, default=CHUNKS_FILE)
    args = parser.parse_args()
    build_index(args.chunk_size, args.overlap, args.collection, args.chunks_file)
