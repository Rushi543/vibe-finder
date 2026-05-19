from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")


def build_spotify_corpus(spotify_data: dict) -> list[str]:
    """Turn Spotify data into text chunks to embed."""
    chunks = []

    for artist in spotify_data.get("top_artists", []):
        parts = [artist["name"]] + artist.get("genres", [])
        chunks.append(" ".join(parts))

    for track in spotify_data.get("top_tracks", []):
        parts = [track["name"], track["artist"]]
        chunks.append(" ".join(parts))

    for genre in spotify_data.get("top_genres", []):
        chunks.append(genre)

    return chunks


def embed_spotify_data(spotify_data: dict) -> tuple[list[float], dict]:
    """
    Embed a user's Spotify data into a single vector.
    Returns (vector, metadata).
    """
    chunks = build_spotify_corpus(spotify_data)

    if not chunks:
        chunks = ["music listener"]

    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    user_vector = np.mean(embeddings, axis=0)

    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector = user_vector / norm

    # Count genre frequency
    from collections import Counter
    genre_counter = Counter()
    for artist in spotify_data.get("top_artists", []):
        for genre in artist.get("genres", []):
            genre_counter[genre] += 1

    metadata = {
        "top_artists": [a["name"] for a in spotify_data.get("top_artists", [])[:5]],
        "top_genres": [g for g, _ in genre_counter.most_common(8)],
        "top_tracks": [t["name"] for t in spotify_data.get("top_tracks", [])[:5]],
    }

    return user_vector.tolist(), metadata