from embedding_model import get_embedding_model


def embed_anilist_data(anilist_data: dict) -> tuple[list, dict]:
    """
    Convert AniList data to a vector and metadata.
    Returns (vector, metadata)
    """
    completed_anime = anilist_data.get("completed_anime", [])
    all_genres = anilist_data.get("all_genres", [])
    studios = anilist_data.get("studios", [])
    top_favorites = anilist_data.get("top_favorites", [])
    top_fav_manga = anilist_data.get("top_fav_manga", [])

    # Build text representation
    text_parts = []

    if completed_anime:
        text_parts.append(f"Watched anime: {', '.join(completed_anime[:10])}")

    if all_genres:
        text_parts.append(f"Favorite genres: {', '.join(all_genres[:5])}")

    if studios:
        text_parts.append(f"Favorite studios: {', '.join(studios[:3])}")

    if top_favorites:
        text_parts.append(f"Favorites: {', '.join(top_favorites[:5])}")

    anime_count = anilist_data.get("anime_count", 0)
    manga_count = anilist_data.get("manga_count", 0)
    anime_score = anilist_data.get("anime_score", 0)
    manga_score = anilist_data.get("manga_score", 0)

    text_parts.append(f"Watched {anime_count} anime with average score {anime_score:.1f}")
    if manga_count > 0:
        text_parts.append(f"Read {manga_count} manga with average score {manga_score:.1f}")

    full_text = " ".join(text_parts)

    # Generate embedding
    vector = get_embedding_model().encode(full_text, convert_to_tensor=True).tolist()

    # Top 3 genres
    top_genres = all_genres[:3] if all_genres else []

    metadata = {
        "anilist": {
            "username": anilist_data.get("username", ""),
            "top_anime": completed_anime[:5],
            "top_genres": top_genres,
            "top_favorites": top_favorites[:5],
            "top_fav_manga": top_fav_manga[:5],
            "top_studios": studios[:3],
            "anime_count": anime_count,
            "manga_count": manga_count,
        }
    }

    return vector, metadata
