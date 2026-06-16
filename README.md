# F1 Hybrid RAG

> Final assignment for the course **Machine Learning, Theory and Practical Application**.

A fully local RAG system that answers Formula 1 questions using a corpus of Wikipedia and F1 Fandom wiki articles. No API keys, no cloud, runs entirely on your machine with Ollama.

## Stack

- Embeddings: nomic-embed-text via Ollama
- Vector store: ChromaDB (local, persistent)
- Keyword search: BM25 (rank-bm25)
- Fusion: Reciprocal Rank Fusion (RRF)
- Generation: llama3.2 via Ollama
- UI: Streamlit

## Corpus

Data is pulled from two sources:

- **Wikipedia** — ~50 articles via the wikipedia-api library covering drivers, teams, circuits, seasons and technical topics
- **F1 Fandom wiki** — ~25 articles via the MediaWiki API at f1.fandom.com, community-written content that gives different coverage of the same subjects

Running `fetch_data.py` downloads everything and saves it to `data/`. Wikipedia files are saved as `Title.txt`, fandom files as `fandom_Title.txt`.

## Setup

    # 1. install Ollama and pull the models you need
    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull nomic-embed-text
    ollama pull llama3.2

    # 2. install python deps
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

## Running

    python fetch_data.py    # download articles from Wikipedia + Fandom
    python ingest.py        # chunk, embed and store in ChromaDB (takes a few minutes)
    streamlit run app.py    # start the app

## Evaluation

See `notebooks/evalutation.ipynb`. It has a 162-question test set written to cover all article categories, a hit rate comparison between naive (dense only) and hybrid (RRF) retrieval at k=1,3,5,8, a per-category breakdown at k=5, a comparison plot, and failure case analysis.

To re-run evaluation just open the notebook and run all cells. Make sure Ollama is running first.
