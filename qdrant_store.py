import os
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    PayloadSchemaType
)
from dotenv import load_dotenv
import hashlib

load_dotenv()

COLLECTION_NAME = "vibe_users"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

def ensure_collection():
    """Create collection if it doesn't exist."""
    if not client.collection_exists(collection_name=COLLECTION_NAME):

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        print(f"Created collection: {COLLECTION_NAME}")

        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="username",
            field_schema=PayloadSchemaType.KEYWORD,
        )

        print(f"Payload schema created")

def fuse_vectors(source_vectors: dict, weights: dict) -> list:
    """Weighted average of source vectors, normalized."""
    available = {k: v for k, v in weights.items() if k in source_vectors}
    total = sum(available.values())
    if total == 0:
        available = {k: 1.0 for k in source_vectors}
        total = len(source_vectors)

    result = np.zeros(VECTOR_SIZE)
    for source, weight in available.items():
        result += (weight / total) * np.array(source_vectors[source])

    norm = np.linalg.norm(result)
    if norm > 0:
        result = result / norm

    return result.tolist()


def store_user_vector(
    username: str,
    source_vectors: dict,
    metadata: dict,
    weights: dict = None,
    seeded: bool = False,
):
    """
    Store a user with per-source vectors in payload.
    source_vectors: { "github": [...], "spotify": [...] }
    metadata:       { "github": {...}, "spotify": {...} }
    """
    ensure_collection()
    point_id = get_point_id(username)

    # Fetch existing to merge sources
    existing = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
        with_vectors=False,
    )

    merged_source_vectors = {}
    merged_metadata = {}
    if existing:
        merged_source_vectors = existing[0].payload.get("source_vectors", {})
        merged_metadata = existing[0].payload.get("source_metadata", {})

    merged_source_vectors.update(source_vectors)
    merged_metadata.update(metadata)

    equal_weights = {s: 1.0 for s in merged_source_vectors}
    fused = fuse_vectors(merged_source_vectors, equal_weights)

    github_meta = merged_metadata.get("github", {})
    spotify_meta = merged_metadata.get("spotify", {})

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=fused,
                payload={
                    "username": username,
                    "source_vectors": merged_source_vectors,
                    "source_metadata": merged_metadata,
                    "sources": list(merged_source_vectors.keys()),
                    "seeded": seeded,
                    "top_languages": github_meta.get("top_languages", []),
                    "top_topics": github_meta.get("top_topics", []),
                    "top_genres": spotify_meta.get("top_genres", []),
                    "top_artists": spotify_meta.get("top_artists", []),
                },
            )
        ],
    )
    print(f"Stored {username} | sources: {list(merged_source_vectors.keys())}")

def get_point_id(username: str) -> int:
    digest = hashlib.sha256(username.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)

def find_similar_users(username: str, top_k: int = 5):
    ensure_collection()
    point_id = get_point_id(username)
    results = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_vectors=True,
    )
    if not results:
        return None
    return _search_similar(results[0].vector, username, top_k)


def find_similar_weighted(username: str, weights: dict, top_k: int = 5):
    """Recompute query vector with custom weights, no re-indexing needed."""
    ensure_collection()
    point_id = get_point_id(username)
    results = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
        with_vectors=False,
    )
    if not results:
        return None
    source_vectors = results[0].payload.get("source_vectors", {})
    if not source_vectors:
        return None
    query_vector = fuse_vectors(source_vectors, weights)
    return _search_similar(query_vector, username, top_k)


def _search_similar(query_vector: list, exclude_username: str, top_k: int) -> list:
    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k + 1,
        with_payload=True,
        query_filter=Filter(
            must_not=[
                FieldCondition(
                    key="username",
                    match=MatchValue(value=exclude_username),
                )
            ]
        ),
    )
    return [
        {
            "username": hit.payload["username"],
            "similarity": round(hit.score, 4),
            "top_languages": hit.payload.get("top_languages", []),
            "top_topics": hit.payload.get("top_topics", []),
            "top_genres": hit.payload.get("top_genres", []),
            "top_artists": hit.payload.get("top_artists", []),
            "sources": hit.payload.get("sources", []),
        }
        for hit in hits.points
    ]


def list_all_users() -> list:
    ensure_collection()
    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    return [
        {
            "username": r.payload["username"],
            "top_languages": r.payload.get("top_languages", []),
            "top_topics": r.payload.get("top_topics", []),
            "top_genres": r.payload.get("top_genres", []),
            "sources": r.payload.get("sources", []),
            "seeded": r.payload.get("seeded", False),
        }
        for r in results
    ]
