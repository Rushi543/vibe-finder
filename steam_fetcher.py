import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_API = "https://api.steampowered.com"
STORE_API = "https://store.steampowered.com/api"


async def resolve_steam_id(identifier: str, client: httpx.AsyncClient) -> str | None:
    """
    Resolve a Steam vanity URL or numeric ID to a Steam64 ID.
    Accepts: numeric ID, full profile URL, or vanity name.
    """
    # Already a numeric Steam64 ID
    identifier = identifier.strip()
    if identifier.isdigit() and len(identifier) >= 15:
        return identifier

    # Extract vanity from full URL
    if "steamcommunity.com" in identifier:
        parts = identifier.rstrip("/").split("/")
        identifier = parts[-1]

    # Resolve vanity name
    res = await client.get(
        f"{STEAM_API}/ISteamUser/ResolveVanityURL/v1/",
        params={"key": STEAM_API_KEY, "vanityurl": identifier},
        timeout=10.0,
    )
    data = res.json().get("response", {})
    if data.get("success") == 1:
        return data["steamid"]
    return None


async def get_game_details(app_id: int, client: httpx.AsyncClient) -> dict:
    """Fetch genres and tags for a game from Steam Store API."""
    try:
        res = await client.get(
            f"{STORE_API}/appdetails",
            params={"appids": app_id, "filters": "genres"},
            timeout=8.0,
        )
        data = res.json().get(str(app_id), {})
        if not data.get("success"):
            return {}
        app_data = data.get("data", {})
        genres = [g["description"] for g in app_data.get("genres", [])]
        return {"genres": genres}
    except Exception:
        return {}


async def fetch_steam_data(identifier: str) -> dict | None:
    """
    Fetch a user's Steam library with game details.
    identifier: Steam profile URL, vanity name, or Steam64 ID
    """
    async with httpx.AsyncClient() as client:
        steam_id = await resolve_steam_id(identifier, client)
        if not steam_id:
            return None

        # Get owned games with playtime
        games_res = await client.get(
            f"{STEAM_API}/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": STEAM_API_KEY,
                "steamid": steam_id,
                "include_appinfo": True,
                "include_played_free_games": True,
            },
            timeout=15.0,
        )
        games_data = games_res.json().get("response", {})
        raw_games = games_data.get("games", [])

        if not raw_games:
            return None

        # Sort by playtime, take top 60 most played
        raw_games.sort(key=lambda g: g.get("playtime_forever", 0), reverse=True)
        top_games = raw_games[:60]

        # Fetch genre details for top 20 (store API is slow, limit calls)
        genre_tasks = []
        for game in top_games[:20]:
            genre_tasks.append(get_game_details(game["appid"], client))

        genre_results = await asyncio.gather(*genre_tasks)
        genre_map = {
            top_games[i]["appid"]: genre_results[i]
            for i in range(len(genre_results))
        }

        games = []
        for game in top_games:
            app_id = game["appid"]
            playtime_hours = round(game.get("playtime_forever", 0) / 60, 1)
            details = genre_map.get(app_id, {})
            games.append({
                "app_id": app_id,
                "name": game.get("name", f"App {app_id}"),
                "playtime_hours": playtime_hours,
                "genres": details.get("genres", []),
                "tags": [],  # Steam tags require scraping, skip for now
            })

        return {
            "steam_id": steam_id,
            "games": games,
            "total_games": len(raw_games),
        }