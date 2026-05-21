import os
import streamlit as st
from src.hybrid_rag import build_index, answer_question


UPLOAD_DIR = "data/uploads"

st.set_page_config(
    page_title="Hybrid RAG Business Assistant",
    page_icon="🤖",
    layout="wide"
)

st.title("Hybrid RAG Business Assistant")

st.write(
    "Local AI assistant using Hybrid RAG: semantic search + keyword search "
    "across PDF, DOCX, and TXT business documents."
)

with st.sidebar:
    st.header("Project Information")
    st.write("Hybrid RAG")
    st.write("PDF / DOCX / TXT Ingestion")
    st.write("Multiple Document Support")
    st.write("Dynamic Indexing")
    st.write("Local LLM with Ollama")
    st.write("No API Keys Required")

    st.divider()

    uploaded_files = st.file_uploader(
        "Upload business documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )

    if uploaded_files:
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        for uploaded_file in uploaded_files:
            file_path = os.path.join(UPLOAD_DIR, uploaded_file.name)

            with open(file_path, "wb") as file:
                file.write(uploaded_file.getbuffer())

        st.success(f"{len(uploaded_files)} file(s) uploaded successfully.")

    if st.button("Build / Rebuild Index"):
        with st.spinner("Indexing uploaded documents..."):
            chunk_count = build_index()

        st.success(f"Index created successfully with {chunk_count} chunks.")

st.subheader("Ask a Business Question")

query = st.text_area(
    "Enter your question:",
    placeholder="Example: What is the escalation process for delayed tickets?"
)

if st.button("Generate Answer"):

    if not query.strip():
        st.warning("Please enter a question.")

    else:
        with st.spinner("Running Hybrid RAG retrieval..."):
            answer, sources = answer_question(query)

        st.subheader("Answer")
        st.write(answer)

        st.subheader("Retrieved Source Chunks")

        for index, source in enumerate(sources, start=1):
            with st.expander(
                f"Source Chunk {index} | {source['source']} | {source['retrieval_type']}"
            ):
                st.write(source["content"])