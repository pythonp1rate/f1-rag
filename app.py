import time
import streamlit as st
from rag import ask_hybrid, ask_naive, dense_retrieve, sparse_retrieve, reciprocal_rank_fusion, get_corpus_stats

st.set_page_config(page_title="F1 RAG", layout="wide")

stats = get_corpus_stats()

with st.sidebar:
    st.header("System")
    st.markdown(f"**Embedding:** nomic-embed-text (Ollama)")
    st.markdown(f"**Generation:** llama3.2 (Ollama)")
    st.markdown(f"**Vector store:** ChromaDB (local)")
    st.markdown(f"**Keyword search:** BM25 via rank-bm25")
    st.markdown(f"**Fusion:** Reciprocal Rank Fusion (k=60)")
    st.markdown(f"**Corpus:** {stats['chunks']} chunks from {stats['articles']} articles")
    st.markdown(f"**Sources:** Wikipedia + F1 Fandom wiki")

    st.divider()

    st.header("Settings")
    top_k = st.slider("Chunks to retrieve (k)", 2, 10, 6)

    st.divider()

    st.header("Example questions")
    examples = [
        "What happened at the 2021 Abu Dhabi Grand Prix?",
        "What caused Grosjean's crash in Bahrain 2020?",
        "How does DRS work?",
        "How many championships did Schumacher win?",
        "What is porpoising and why was it a problem in 2022?",
        "Which team dominated the hybrid era?",
        "Who had more podiums in total, Senna or Prost?",
        "What lap did the Safety Car come out in the 2021 Abu Dhabi finale?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True):
            st.session_state["query"] = ex

st.title("F1 Encyclopedia — Hybrid RAG")
st.caption(
    "Dense retrieval (nomic-embed-text + ChromaDB) and sparse retrieval (BM25) "
    "fused with Reciprocal Rank Fusion. Fully local — no API keys, no cost per query."
)

query = st.text_input(
    "Ask a question about Formula 1:",
    value=st.session_state.get("query", ""),
    placeholder="e.g. Who won the 2021 championship and how controversial was it?"
)

if query:
    t0 = time.time()
    dense  = dense_retrieve(query, k=20)
    sparse = sparse_retrieve(query, k=20)
    fused  = reciprocal_rank_fusion(dense, sparse)
    hybrid_chunks = fused[:top_k]
    retrieval_time = time.time() - t0

    from rag import generate
    t1 = time.time()
    hybrid_answer = generate(query, hybrid_chunks)
    gen_time = time.time() - t1

    naive_chunks = dense[:top_k]
    naive_answer = generate(query, naive_chunks)

    unique_sources = set(c["source"] for c in hybrid_chunks)
    hybrid_sources = set(c["source"] for c in hybrid_chunks)
    naive_sources  = set(c["source"] for c in naive_chunks)
    only_hybrid    = hybrid_sources - naive_sources
    only_naive     = naive_sources  - hybrid_sources
    in_both        = hybrid_sources & naive_sources

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Chunks retrieved", top_k)
    c2.metric("Unique articles", len(unique_sources))
    c3.metric("Retrieval time", f"{retrieval_time:.2f}s")
    c4.metric("Generation time", f"{gen_time:.2f}s")

    st.divider()

    tab_answer, tab_sources, tab_compare = st.tabs(["Answer", "Retrieved Chunks", "Hybrid vs Naive"])

    with tab_answer:
        st.subheader("Answer (Hybrid RAG)")
        st.markdown(hybrid_answer)

        st.divider()
        st.caption("Sources used to generate this answer:")
        source_list = ", ".join(sorted(unique_sources))
        st.markdown(source_list)

    with tab_sources:
        st.markdown(
            "Chunks are ranked by RRF score — higher means both dense and sparse retrieval "
            "agreed this chunk is relevant. Lower cosine distance = more semantically similar to the query."
        )

        max_rrf = hybrid_chunks[0]["rrf_score"] if hybrid_chunks else 1

        for i, chunk in enumerate(hybrid_chunks):
            rrf   = chunk.get("rrf_score", 0)
            dist  = chunk.get("distance", None)
            label = chunk["source"]

            with st.expander(f"Chunk {i+1} — {label}"):
                score_col, text_col = st.columns([1, 3])
                with score_col:
                    st.metric("RRF score", f"{rrf:.4f}")
                    st.progress(rrf / max_rrf)
                    if dist is not None:
                        st.metric("Cosine dist", f"{dist:.4f}")
                with text_col:
                    st.markdown(chunk["text"])

    with tab_compare:
        st.markdown(
            "Same query, two retrieval methods. "
            "Hybrid uses both dense embeddings and BM25 keyword matching fused with RRF. "
            "Naive uses only the dense embeddings."
        )

        if only_hybrid:
            st.success(f"Only in hybrid: {', '.join(sorted(only_hybrid))}")
        if only_naive:
            st.warning(f"Only in naive: {', '.join(sorted(only_naive))}")
        if in_both:
            st.info(f"In both: {', '.join(sorted(in_both))}")

        st.divider()

        col_h, col_n = st.columns(2)

        with col_h:
            st.subheader("Hybrid (RRF)")
            max_rrf = hybrid_chunks[0]["rrf_score"] if hybrid_chunks else 1
            for i, chunk in enumerate(hybrid_chunks):
                rrf = chunk.get("rrf_score", 0)
                tag = ""
                if chunk["source"] in only_hybrid:
                    tag = " — unique to hybrid"
                st.markdown(f"**{i+1}. {chunk['source']}**{tag}")
                st.progress(rrf / max_rrf)
                st.caption(f"RRF score: {rrf:.4f}")

        with col_n:
            st.subheader("Naive (dense only)")
            max_dist = max((c.get("distance", 1) for c in naive_chunks), default=1)
            for i, chunk in enumerate(naive_chunks):
                dist = chunk.get("distance", 0)
                tag = ""
                if chunk["source"] in only_naive:
                    tag = " — unique to naive"
                st.markdown(f"**{i+1}. {chunk['source']}**{tag}")
                similarity = max(0, 1 - dist / 2)
                st.progress(similarity)
                st.caption(f"Cosine dist: {dist:.4f}")

        st.divider()
        st.subheader("Answers side by side")
        ans_h, ans_n = st.columns(2)
        with ans_h:
            st.markdown("**Hybrid answer**")
            st.markdown(hybrid_answer)
        with ans_n:
            st.markdown("**Naive answer**")
            st.markdown(naive_answer)
