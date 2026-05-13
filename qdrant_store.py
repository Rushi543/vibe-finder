import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "vibe_users"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output size

client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)


def ensure_collection():
    """Create collection if it doesn't exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        print(f"Created collection: {COLLECTION_NAME}")


def store_user_vector(username: str, vector: list[float], metadata: dict):
    """Store or overwrite a user's vector in Qdrant."""
    ensure_collection()

    # Use a stable integer ID derived from username hash
    point_id = abs(hash(username)) % (2**63)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "username": username,
                    "top_languages": metadata.get("top_languages", []),
                    "top_topics": metadata.get("top_topics", []),
                    "total_items": metadata.get("total_items", 0),
                    "source": "github",
                },
            )
        ],
    )
    print(f"Stored vector for {username} (id={point_id})")


def find_similar_users(username: str, top_k: int = 5) -> list[dict] | None:
    """Find users most similar to the given username."""
    ensure_collection()

    point_id = abs(hash(username)) % (2**63)

    # Retrieve the user's vector first
    results = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_vectors=True,
    )

    if not results:
        return None

    user_vector = results[0].vector

    # Search for similar users, excluding self
    hits = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=user_vector,
        limit=top_k + 1,  # +1 because self will be in results
        with_payload=True,
        query_filter=Filter(
            must_not=[
                FieldCondition(
                    key="username",
                    match=MatchValue(value=username),
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
        }
        for hit in hits
    ]


def list_all_users() -> list[dict]:
    """Return all stored users with their metadata."""
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
        }
        for r in results
    ]