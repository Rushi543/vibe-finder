from collections import Counter
from sentence_transformers import SentenceTransformer
import numpy as np

# Load once at module level — this downloads ~90MB on first run
model = SentenceTransformer("all-MiniLM-L6-v2")


def build_text_corpus(github_data: dict) -> list[str]:
    """Turn GitHub data into a list of text chunks to embed."""
    chunks = []

    for repo in github_data["starred"] + github_data["repos"]:
        parts = []

        if repo["name"]:
            parts.append(repo["name"].replace("-", " ").replace("_", " "))

        if repo["description"]:
            parts.append(repo["description"])

        if repo["language"]:
            parts.append(repo["language"])

        if repo["topics"]:
            parts.extend(repo["topics"])

        if parts:
            chunks.append(" ".join(parts))

    return chunks


def compute_metadata(github_data: dict) -> dict:
    """Extract useful metadata for display / payload storage."""
    all_items = github_data["starred"] + github_data["repos"]

    lang_counter = Counter()
    topic_counter = Counter()

    for item in all_items:
        if item["language"]:
            lang_counter[item["language"]] += 1
        for topic in item["topics"]:
            topic_counter[topic] += 1

    return {
        "username": github_data["username"],
        "top_languages": [lang for lang, _ in lang_counter.most_common(5)],
        "top_topics": [topic for topic, _ in topic_counter.most_common(10)],
        "total_items": len(all_items),
    }


def embed_github_data(github_data: dict) -> tuple[list[float], dict]:
    """
    Embed a user's GitHub data into a single vector.
    Returns (vector, metadata).
    """
    chunks = build_text_corpus(github_data)
    metadata = compute_metadata(github_data)

    if not chunks:
        # Fallback: embed just the username
        chunks = [github_data["username"]]

    # Embed all chunks, then average-pool into one vector
    embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    user_vector = np.mean(embeddings, axis=0)

    # Normalize to unit length (better cosine similarity in Qdrant)
    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector = user_vector / norm

    return user_vector.tolist(), metadata