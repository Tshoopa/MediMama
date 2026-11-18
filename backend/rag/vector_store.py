# backend/rag/vector_store.py

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    SparseVectorParams,
    SparseIndexParams,
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
    if settings.qdrant_url.strip():
        return QdrantClient(
            url=settings.qdrant_url.strip(),
            api_key=settings.qdrant_api_key.strip() or None,
        )
    if settings.qdrant_path:
        return QdrantClient(path=str(settings.qdrant_path))
    return QdrantClient(url=f"http://{settings.qdrant_host}:{settings.qdrant_port}")


def ensure_collection(client: QdrantClient, vector_size: int):
    collection_name = settings.active_collection_name
    existing = {collection.name for collection in client.get_collections().collections}
    if collection_name not in existing:
        client.create_collection(
            collection_name=collection_name,
            vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams(index=SparseIndexParams())},
        )
    else:
        info = client.get_collection(collection_name)
        dense_config = info.config.params.vectors
        dense_config = dense_config.get("dense") if isinstance(dense_config, dict) else dense_config
        existing_size = getattr(dense_config, "size", None)
        if existing_size is not None and int(existing_size) != int(vector_size):
            raise RuntimeError(
                f"Qdrant collection '{collection_name}' has dense dimension {existing_size}, "
                f"but the selected embedding backend returns {vector_size}. Use a different "
                "COLLECTION_NAME or delete/re-ingest this collection."
            )

    for field, schema in PAYLOAD_INDEXES.items():
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=schema,
            )
        except Exception:
            pass  # index may already exist
