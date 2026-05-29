from sentence_transformers import SentenceTransformer
import numpy as np
from collections import Counter

model = None


def get_model():
    global model
    if model is None:
        model = SentenceTransformer("all-MiniLM-L6-v2")
    return model

# Genre/tag mappings for common Steam app IDs
# We'll enrich this via the Steam store API per game
STEAM_GENRE_CACHE = {}


def build_steam_corpus(steam_data: dict) -> list:
    """Turn Steam library into weighted text chunks."""
    chunks = []

    for game in steam_data.get("games", []):
        name = game.get("name", "")
        genres = game.get("genres", [])
        tags = game.get("tags", [])
        playtime = game.get("playtime_hours", 0)

        if not name:
            continue

        parts = [name] + genres + tags
        text = " ".join(parts)

        # Weight by playtime — repeat chunk proportionally
        # Cap at 10x to avoid one game dominating
        weight = min(int(playtime / 10) + 1, 10)
        chunks.extend([text] * weight)

    return chunks if chunks else ["gamer"]


def embed_steam_data(steam_data: dict) -> tuple:
    """
    Embed a user's Steam library into a single vector.
    Returns (vector, metadata).
    """
    chunks = build_steam_corpus(steam_data)

    embeddings = get_model().encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    user_vector = np.mean(embeddings, axis=0)

    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector = user_vector / norm

    # Compute metadata
    genre_counter = Counter()
    tag_counter = Counter()
    top_games = sorted(steam_data.get("games", []), key=lambda g: g.get("playtime_hours", 0), reverse=True)

    for game in steam_data.get("games", []):
        for genre in game.get("genres", []):
            genre_counter[genre] += 1
        for tag in game.get("tags", []):
            tag_counter[tag] += 1

    metadata = {
        "steam": {
            "top_games": [g["name"] for g in top_games[:5]],
            "top_genres": [g for g, _ in genre_counter.most_common(8)],
            "top_tags": [t for t, _ in tag_counter.most_common(10)],
            "total_games": len(steam_data.get("games", [])),
        }
    }

    return user_vector.tolist(), metadata
