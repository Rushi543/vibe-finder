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

    usernames = []
    vectors = []
    payloads = []

    for r in results:
        usernames.append(r.payload["username"])
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
    for i, username in enumerate(usernames):
        output.append({
            "username": username,
            "x": round(float(coords_3d[i, 0]), 4),
            "y": round(float(coords_3d[i, 1]), 4),
            "z": round(float(coords_3d[i, 2]), 4),
            "top_languages": payloads[i].get("top_languages", []),
            "top_topics": payloads[i].get("top_topics", []),
            "seeded": payloads[i].get("seeded", False),
            "source": payloads[i].get("source", "github"),
        })

    return output