import os
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
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
            field_name="user_id",
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


def _merge_list_values(*values: list) -> list:
    merged = []
    for value in values:
        for item in value or []:
            if item not in merged:
                merged.append(item)
    return merged


def _normalize_payload(payload: dict) -> dict:
    source_vectors = payload.get("source_vectors", {})
    sources = payload.get("sources")
    if not sources:
        sources = list(source_vectors.keys())
    if not sources and payload.get("source"):
        sources = [payload["source"]]

    user_id = payload.get("user_id") or payload.get("username")
    github_username = payload.get("github_username")
    if not github_username and payload.get("username") and "github" in sources:
        github_username = payload["username"]

    label = payload.get("label") or payload.get("username") or user_id

    return {
        "user_id": user_id,
        "label": label,
        "github_username": github_username,
        "sources": sources,
        "seeded": payload.get("seeded", False),
        "top_languages": payload.get("top_languages", []),
        "top_topics": payload.get("top_topics", []),
        "top_games": payload.get("top_games", []),
        "top_genres": payload.get("top_genres", []),
    }


def store_user_vector(
    user_id: str,
    source_vectors: dict,
    metadata: dict,
    seeded: bool = False,
    label: str | None = None,
    github_username: str | None = None,
):
    """
    Store a user with per-source vectors in payload.
    source_vectors: { "github": [...], "spotify": [...] }
    metadata:       { "github": {...}, "spotify": {...} }
    """
    ensure_collection()
    point_id = get_point_id(user_id)

    # Fetch existing to merge sources
    existing = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
        with_vectors=False,
    )

    merged_source_vectors = {}
    merged_metadata = {}
    existing_payload = {}
    if existing:
        existing_payload = existing[0].payload
        merged_source_vectors = existing_payload.get("source_vectors", {})
        merged_metadata = existing_payload.get("source_metadata", {})

    merged_source_vectors.update(source_vectors)
    merged_metadata.update(metadata)

    equal_weights = {s: 1.0 for s in merged_source_vectors}
    fused = fuse_vectors(merged_source_vectors, equal_weights)

    github_meta = merged_metadata.get("github", {})
    steam_meta = merged_metadata.get("steam", {})
    anilist_meta = merged_metadata.get("anilist", {})
    spotify_meta = merged_metadata.get("spotify", {})
    merged_seeded = seeded and existing_payload.get("seeded", seeded) if existing_payload else seeded
    merged_label = label or existing_payload.get("label") or user_id
    merged_github_username = (
        github_username
        or existing_payload.get("github_username")
        or (existing_payload.get("username") if "github" in merged_source_vectors else None)
    )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=fused,
                payload={
                    "user_id": user_id,
                    "username": user_id,
                    "label": merged_label,
                    "github_username": merged_github_username,
                    "source_vectors": merged_source_vectors,
                    "source_metadata": merged_metadata,
                    "sources": list(merged_source_vectors.keys()),
                    "seeded": merged_seeded,
                    "top_languages": github_meta.get("top_languages", []),
                    "top_topics": github_meta.get("top_topics", []),
                    "top_games": steam_meta.get("top_games", []),
                    "top_anime": anilist_meta.get("top_anime", []),
                    "top_favorites": anilist_meta.get("top_favorites", []),
                    "top_genres": _merge_list_values(
                        steam_meta.get("top_genres", []),
                        spotify_meta.get("top_genres", []),
                        anilist_meta.get("top_genres", []),
                    ),
                    "top_artists": spotify_meta.get("top_artists", []),
                },
            )
        ],
    )
    print(f"Stored {user_id} | sources: {list(merged_source_vectors.keys())}")


def get_point_id(user_id: str) -> int:
    digest = hashlib.sha256(user_id.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def get_user_profile(user_id: str) -> dict | None:
    ensure_collection()
    point_id = get_point_id(user_id)
    results = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_payload=True,
        with_vectors=False,
    )
    if not results:
        return None
    return _normalize_payload(results[0].payload)


def find_similar_users(user_id: str, top_k: int = 5):
    ensure_collection()
    point_id = get_point_id(user_id)
    results = client.retrieve(
            "top_games": payload.get("top_games", []),
            "top_anime": payload.get("top_anime", []),
            "top_favorites": payload.get("top_favorites", []),
            "top_genres": payload.get("top_genres", []),
        with_vectors=True,
    )
    if not results:
        return None
    exclude_username = None
    if results[0].payload:
        exclude_username = results[0].payload.get("username")
    return _search_similar(results[0].vector, user_id, top_k, exclude_username)


def find_similar_weighted(user_id: str, weights: dict, top_k: int = 5):
    """Recompute query vector with custom weights, no re-indexing needed."""
    ensure_collection()
    point_id = get_point_id(user_id)
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
    return _search_similar(query_vector, user_id, top_k, results[0].payload.get("username"))


def _search_similar(
    query_vector: list,
    exclude_user_id: str,
    top_k: int,
    exclude_username: str | None = None,
) -> list:
    exclude_values = {exclude_user_id}
    if exclude_username:
        exclude_values.add(exclude_username)

    hits = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=top_k + 20,
        with_payload=True,
    )
    matches = []
    for hit in hits.points:
        payload = hit.payload or {}
        normalized = _normalize_payload(payload)
        hit_ids = {
            normalized.get("user_id"),
            payload.get("username"),
        }
        if exclude_values.intersection(hit_id for hit_id in hit_ids if hit_id):
            continue

        matches.append(normalized | {"similarity": round(hit.score, 4)})
        if len(matches) >= top_k:
            break

    return matches


def list_all_users() -> list:
    ensure_collection()
    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=100,
        with_payload=True,
        with_vectors=False,
    )
    return [_normalize_payload(r.payload) for r in results]
