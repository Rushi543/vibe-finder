import numpy as np
from umap import UMAP
from qdrant_store import client, COLLECTION_NAME, ensure_collection


def compute_umap_3d() -> list[dict]:
    """
    Fetch all user vectors from Qdrant, run UMAP to 3D, return coordinates with metadata.
    """
    ensure_collection()

    # Scroll through all points with vectors
    results, _ = client.scroll(
        collection_name=COLLECTION_NAME,
        limit=500,
        with_payload=True,
        with_vectors=True,
    )

    if len(results) < 2:
        return []

    user_ids = []
    vectors = []
    payloads = []

    for r in results:
        user_ids.append(r.payload.get("user_id") or r.payload.get("username"))
        vectors.append(r.vector)
        payloads.append(r.payload)

    matrix = np.array(vectors)

    # UMAP to 3D
    # n_neighbors controls local vs global structure — 10 is good for <100 points
    n_neighbors = min(10, len(matrix) - 1)
    reducer = UMAP(
        n_components=3,
        n_neighbors=n_neighbors,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
    )
    coords_3d = reducer.fit_transform(matrix)

    # Normalize coords to [-1, 1] range for easier Three.js rendering
    for i in range(3):
        col = coords_3d[:, i]
        col_range = col.max() - col.min()
        if col_range > 0:
            coords_3d[:, i] = 2 * (col - col.min()) / col_range - 1

    output = []
    for i, user_id in enumerate(user_ids):
        output.append({
            "user_id": payloads[i].get("user_id") or payloads[i].get("username") or user_id,
            "label": payloads[i].get("label") or payloads[i].get("username") or user_id,
            "github_username": payloads[i].get("github_username"),
            "x": round(float(coords_3d[i, 0]), 4),
            "y": round(float(coords_3d[i, 1]), 4),
            "z": round(float(coords_3d[i, 2]), 4),
            "sources": payloads[i].get("sources", list(payloads[i].get("source_vectors", {}).keys())),
            "top_languages": payloads[i].get("top_languages", []),
            "top_topics": payloads[i].get("top_topics", []),
            "top_games": payloads[i].get("top_games", []),
            "top_genres": payloads[i].get("top_genres", []),
            "seeded": payloads[i].get("seeded", False),
        })

    return output
