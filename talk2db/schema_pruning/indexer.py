import os
import uuid
from typing import List, Optional
import chromadb
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from talk2db.config import DEFAULT_EMBEDDING_MODEL
from talk2db.database.inspector import DatabaseCatalog


class SchemaVectorIndex:
    """Indexes database schema descriptors in ChromaDB for fast table retrieval."""

    def __init__(self, catalog: DatabaseCatalog, embedding_model: Optional[str] = None):
        self.catalog = catalog
        self.model_name = embedding_model or DEFAULT_EMBEDDING_MODEL
        self.table_names: List[str] = []
        self.descriptors: List[str] = []
        self._client: Optional[chromadb.EphemeralClient] = None
        self._collection = None
        self._embeddings_client: Optional[GoogleGenerativeAIEmbeddings] = None

        self._build_index()

    def _get_embeddings_client(self) -> Optional[GoogleGenerativeAIEmbeddings]:
        if self._embeddings_client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if api_key:
                self._embeddings_client = GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=api_key,
                )
        return self._embeddings_client

    def _build_index(self) -> None:
        self.table_names = list(self.catalog.tables.keys())
        if not self.table_names:
            return

        self.descriptors = [
            self.catalog.tables[t].to_descriptor() for t in self.table_names
        ]

        # In-memory Chroma client for session isolation
        self._client = chromadb.EphemeralClient()
        coll_name = f"schema_{uuid.uuid4().hex[:8]}"
        self._collection = self._client.create_collection(
            name=coll_name,
            metadata={"hnsw:space": "cosine"}
        )

        try:
            embed_client = self._get_embeddings_client()
            if embed_client:
                vectors = embed_client.embed_documents(self.descriptors)
                self._collection.add(
                    documents=self.descriptors,
                    embeddings=vectors,
                    ids=self.table_names,
                    metadatas=[{"table": t} for t in self.table_names]
                )
            else:
                self._collection.add(
                    documents=self.descriptors,
                    ids=self.table_names,
                    metadatas=[{"table": t} for t in self.table_names]
                )
        except Exception:
            # Fallback to Chroma's default text embedding if API embeddings fail
            self._collection.add(
                documents=self.descriptors,
                ids=self.table_names,
                metadatas=[{"table": t} for t in self.table_names]
            )

    def search(self, query: str, top_k: int = 5) -> List[str]:
        if not self.table_names:
            return []

        if len(self.table_names) <= top_k:
            return list(self.table_names)

        if self._collection is not None:
            try:
                k = min(top_k, len(self.table_names))
                embed_client = self._get_embeddings_client()
                
                if embed_client:
                    q_vec = embed_client.embed_query(query)
                    res = self._collection.query(query_embeddings=[q_vec], n_results=k)
                else:
                    res = self._collection.query(query_texts=[query], n_results=k)

                matched = []
                if res and res.get("ids"):
                    for table_id in res["ids"][0]:
                        if table_id in self.catalog.tables:
                            matched.append(table_id)
                if matched:
                    return matched
            except Exception:
                pass

        # Simple lexical fallback if vector query fails
        query_words = set(query.lower().replace("_", " ").split())
        ranked = []
        for name, desc in zip(self.table_names, self.descriptors):
            desc_words = set(desc.lower().replace("_", " ").split())
            score = len(query_words.intersection(desc_words))
            ranked.append((score, name))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return [name for _, name in ranked[:top_k]]
