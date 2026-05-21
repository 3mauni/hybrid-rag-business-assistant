import os
import chromadb
import ollama
from pypdf import PdfReader
from docx import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer


UPLOAD_DIR = "data/uploads"
CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "business_docs"

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def read_txt(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        return file.read()


def read_pdf(path):
    reader = PdfReader(path)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text


def read_docx(path):
    doc = Document(path)
    return "\n".join([paragraph.text for paragraph in doc.paragraphs])


def load_file(path):
    extension = os.path.splitext(path)[1].lower()

    if extension == ".txt":
        return read_txt(path)

    if extension == ".pdf":
        return read_pdf(path)

    if extension == ".docx":
        return read_docx(path)

    return ""


def chunk_text(text, chunk_size=700, overlap=150):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def load_all_documents():
    documents = []

    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    for filename in os.listdir(UPLOAD_DIR):
        path = os.path.join(UPLOAD_DIR, filename)

        if os.path.isfile(path):
            text = load_file(path)

            if text.strip():
                chunks = chunk_text(text)

                for chunk in chunks:
                    documents.append(
                        {
                            "source": filename,
                            "content": chunk
                        }
                    )

    return documents


def build_index():
    documents = load_all_documents()

    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(COLLECTION_NAME)

    for index, document in enumerate(documents):
        embedding = embedding_model.encode(document["content"]).tolist()

        collection.add(
            ids=[str(index)],
            documents=[document["content"]],
            embeddings=[embedding],
            metadatas=[
                {
                    "source": document["source"]
                }
            ]
        )

    return len(documents)


def semantic_search(query, top_k=4):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION_NAME)

    query_embedding = embedding_model.encode([query]).tolist()[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k
    )

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]

    return [
        {
            "content": document,
            "source": metadata["source"],
            "retrieval_type": "semantic"
        }
        for document, metadata in zip(documents, metadatas)
    ]


def keyword_search(query, top_k=4):
    documents = load_all_documents()

    if not documents:
        return []

    chunks = [document["content"] for document in documents]
    sources = [document["source"] for document in documents]

    tokenized_chunks = [chunk.lower().split() for chunk in chunks]
    bm25 = BM25Okapi(tokenized_chunks)

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    ranked_results = sorted(
        zip(chunks, sources, scores),
        key=lambda item: item[2],
        reverse=True
    )

    return [
        {
            "content": chunk,
            "source": source,
            "retrieval_type": "keyword"
        }
        for chunk, source, score in ranked_results[:top_k]
    ]


def hybrid_search(query):
    semantic_results = semantic_search(query)
    keyword_results = keyword_search(query)

    combined_results = []
    seen_content = set()

    for result in semantic_results + keyword_results:
        if result["content"] not in seen_content:
            combined_results.append(result)
            seen_content.add(result["content"])

    return combined_results[:6]


def generate_answer(query, retrieved_chunks):
    context = ""

    for item in retrieved_chunks:
        context += f"\nSource: {item['source']}\n"
        context += f"Retrieval Type: {item['retrieval_type']}\n"
        context += f"Content: {item['content']}\n"

    prompt = f"""
You are a professional business operations assistant.

Answer the question using only the provided context.

If the answer is not available in the context, say:
"I do not have enough information in the uploaded documents."

Context:
{context}

Question:
{query}

Answer format:
1. Direct Answer
2. Supporting Details
3. Source Reference
4. Business Recommendation
"""

    response = ollama.chat(
        model="llama3.2:3b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]


def answer_question(query):
    retrieved_chunks = hybrid_search(query)
    answer = generate_answer(query, retrieved_chunks)

    return answer, retrieved_chunks