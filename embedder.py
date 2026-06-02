from collections import Counter
import numpy as np
from embedding_model import get_embedding_model


def build_text_corpus(github_data: dict) -> list:
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


def embed_github_data(github_data: dict) -> tuple:
    """Returns (vector, metadata_dict) where metadata is nested under 'github' key."""
    chunks = build_text_corpus(github_data)
    if not chunks:
        chunks = [github_data["username"]]

    embeddings = get_embedding_model().encode(chunks, convert_to_numpy=True, show_progress_bar=False)
    user_vector = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector = user_vector / norm

    all_items = github_data["starred"] + github_data["repos"]
    lang_counter = Counter()
    topic_counter = Counter()
    for item in all_items:
        if item["language"]:
            lang_counter[item["language"]] += 1
        for topic in item["topics"]:
            topic_counter[topic] += 1

    metadata = {
        "github": {
            "top_languages": [l for l, _ in lang_counter.most_common(5)],
            "top_topics": [t for t, _ in topic_counter.most_common(10)],
            "total_items": len(all_items),
        }
    }

    return user_vector.tolist(), metadata
