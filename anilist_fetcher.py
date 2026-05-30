import httpx


ANILIST_API = "https://graphql.anilist.co"


async def fetch_anilist_data(username: str) -> dict | None:
    """
    Fetch a user's AniList anime/manga list with genres and stats.
    username: AniList username
    """
    async with httpx.AsyncClient() as client:
        # Fetch user ID from username
        # First, fetch the public user profile and favourites in a single query
        user_query = """
        query {
          User(name: "%s") {
            id
            name
            about
            statistics {
              anime { count meanScore }
              manga { count meanScore }
            }
            favourites {
              anime { nodes { id title { romaji english } } }
              manga { nodes { id title { romaji english } } }
            }
          }
        }
        """ % username

        user_res = await client.post(ANILIST_API, json={"query": user_query}, timeout=10.0)
        user_data = user_res.json()
        if user_data.get("errors"):
            return None

        user = user_data.get("data", {}).get("User")
        if not user:
            return None

        user_id = user["id"]

        # Fetch anime list (top 50 most recent)
        anime_query = """
        query {
          Page(page: 1, perPage: 50) {
            mediaList(userId: %d, type: ANIME, sort: UPDATED_TIME_DESC) {
              media {
                id
                title { english romaji }
                genres
                studios { nodes { name } }
                meanScore
                episodes
              }
              status
              score
              progress
            }
          }
        }
        """ % user_id

        anime_res = await client.post(ANILIST_API, json={"query": anime_query}, timeout=15.0)
        anime_data = anime_res.json()

        # Fetch manga list
        manga_query = """
        query {
          Page(page: 1, perPage: 50) {
            mediaList(userId: %d, type: MANGA, sort: UPDATED_TIME_DESC) {
              media { id title { english romaji } genres meanScore chapters }
              status
              score
              progress
            }
          }
        }
        """ % user_id

        manga_res = await client.post(ANILIST_API, json={"query": manga_query}, timeout=15.0)
        manga_data = manga_res.json()

        anime_list = anime_data.get("data", {}).get("Page", {}).get("mediaList", [])
        manga_list = manga_data.get("data", {}).get("Page", {}).get("mediaList", [])

        # Extract genres and studios from watched anime
        all_genres = []
        all_studios = []
        completed_anime = []

        for entry in anime_list:
            if entry.get("status") == "COMPLETED":
                media = entry.get("media", {})
                title = media.get("title", {}).get("english") or media.get("title", {}).get("romaji", "Unknown")
                completed_anime.append(title)

                genres = media.get("genres", [])
                for genre in genres:
                    if genre not in all_genres:
                        all_genres.append(genre)

                studios = media.get("studios", {}).get("nodes", [])
                for studio in studios:
                    studio_name = studio.get("name")
                    if studio_name and studio_name not in all_studios:
                        all_studios.append(studio_name)

        # Favorites from the initial user query
        favourites = user.get("favourites", {})
        fav_anime_nodes = favourites.get("anime", {}).get("nodes", []) if favourites else []
        fav_manga_nodes = favourites.get("manga", {}).get("nodes", []) if favourites else []

        fav_anime = []
        for n in fav_anime_nodes:
            title = n.get("title", {}).get("english") or n.get("title", {}).get("romaji") or "Unknown"
            fav_anime.append(title)

        fav_manga = []
        for n in fav_manga_nodes:
            title = n.get("title", {}).get("english") or n.get("title", {}).get("romaji") or "Unknown"
            fav_manga.append(title)

        # Limit sizes
        completed_anime = completed_anime[:60]

        stats = user.get("statistics", {})
        anime_stats = stats.get("anime", {})
        manga_stats = stats.get("manga", {})

        return {
            "user_id": user_id,
            "username": user["name"],
            "completed_anime": completed_anime[:20],
            "all_genres": all_genres[:30],
            "studios": all_studios[:20],
            "anime_count": anime_stats.get("count", 0),
            "anime_score": anime_stats.get("meanScore", 0) / 10.0,
            "manga_count": manga_stats.get("count", 0),
            "manga_score": manga_stats.get("meanScore", 0) / 10.0,
            "about": user.get("about", ""),
            "top_favorites": fav_anime[:10],
            "top_fav_manga": fav_manga[:10],
        }
