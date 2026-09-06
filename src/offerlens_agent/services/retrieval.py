"""Local vector retrieval for grounding job requirements in resume chunks."""

from __future__ import annotations

import hashlib
import math
import re

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9+#.-]{2,}", lowered)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    chinese_bigrams = [run[index : index + 2] for run in chinese_runs for index in range(max(0, len(run) - 1))]
    return [*latin, *chinese_bigrams]


class HashEmbeddings(Embeddings):
    """Deterministic feature-hashing embeddings for zero-key local demos."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in _tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1 if digest[4] % 2 == 0 else -1
            vector[bucket] += float(sign)
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


class ResumeEvidenceIndex:
    """Chunk and index one resume using LangChain's vector-store contract."""

    def __init__(self, resume_text: str, embeddings: Embeddings | None = None) -> None:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=80,
            separators=["\n\n", "\n", "。", ". ", " ", ""],
        )
        chunks = splitter.split_text(resume_text)
        documents = [
            Document(page_content=chunk, metadata={"source_id": f"resume-chunk-{index}"})
            for index, chunk in enumerate(chunks, start=1)
            if chunk.strip()
        ]
        self._store = InMemoryVectorStore(embedding=embeddings or HashEmbeddings())
        if documents:
            self._store.add_documents(documents)

    def search(self, query: str, k: int = 3) -> list[tuple[Document, float]]:
        """Return the most relevant chunks with normalized similarity scores."""
        return self._store.similarity_search_with_score(query, k=k)
