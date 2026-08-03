# backend/rag/vector_store.py

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    SparseVectorParams, SparseIndexParams,
    PayloadSchemaType,
)
from backend.config import settings

PAYLOAD_INDEXES = {
    "source_type": PayloadSchemaType.KEYWORD,
    "source_name": PayloadSchemaType.KEYWORD,
    "section": PayloadSchemaType.KEYWORD,
    "subsection": PayloadSchemaType.KEYWORD,
    "topic": PayloadSchemaType.KEYWORD,
    "age_group": PayloadSchemaType.KEYWORD,
    "content_type": PayloadSchemaType.KEYWORD,
    "page_start": PayloadSchemaType.INTEGER,
    "page_end": PayloadSchemaType.INTEGER,
    "source_priority": PayloadSchemaType.INTEGER,
}


def get_client(in_memory: bool = False) -> QdrantClient:
    if in_memory:
        return QdrantClient(":memory:")
    if settings.qdrant_path:  # embedded on-disk mode
        return QdrantClient(path=settings.qdrant_path)
    return QdrantClient(url=f"http://{settings.qdrant_host}:{settings.qdrant_port}")


def ensure_collection(client: QdrantClient, vector_size: int):
    existing = {c.name for c in client.get_collections().collections}
    if settings.collection_name not in existing:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams())},
        )

    for field, schema in PAYLOAD_INDEXES.items():
        try:
            client.create_payload_index(
                collection_name=settings.collection_name,
                field_name=field,
                field_schema=schema,
            )
        except Exception:
            pass  # index already exists on re-run