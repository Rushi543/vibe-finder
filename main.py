import base64
import json
import os
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from embedder import embed_github_data
from qdrant_store import (
    find_similar_users,
    find_similar_weighted,
    get_user_profile,
    list_all_users,
    store_user_vector,
)
from spotify_embedder import embed_spotify_data
from steam_embedder import embed_steam_data
from steam_fetcher import fetch_steam_data
from umap_compute import compute_umap_3d

load_dotenv()

app = FastAPI(title="Vibe Finder")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/spotify/callback")
SPOTIFY_SCOPES = "user-top-read user-read-private"


def encode_state(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_state(state: str | None) -> dict:
    if not state:
        return {}

    padding = "=" * (-len(state) % 4)
    try:
        raw = base64.urlsafe_b64decode(f"{state}{padding}".encode("utf-8"))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(400, "Invalid OAuth state")


@app.get("/")
def root():
    return HTMLResponse(
        """
        <h2>Vibe Finder API</h2>
        <p>Use the React app to sign in and connect GitHub or Steam.</p>
        <p><a href="/docs">Open API docs</a></p>
        """
    )


@app.get("/auth/login")
@app.get("/auth/github/start")
def github_login(user_id: str | None = None, label: str | None = None):
    if not user_id:
        raise HTTPException(400, "Missing required query param: user_id")

    state = encode_state({"user_id": user_id, "label": label or user_id})
    query = urlencode(
        {
            "client_id": GITHUB_CLIENT_ID,
            "redirect_uri": GITHUB_REDIRECT_URI,
            "scope": "read:user,public_repo",
            "state": state,
        }
    )
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")


@app.get("/auth/callback")
async def github_callback(code: str, state: str | None = None):
    state_data = decode_state(state)

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
        )

    token = token_res.json().get("access_token")
    if not token:
        raise HTTPException(400, "Failed to get GitHub token")

    await process_github_user(
        token,
        user_id=state_data.get("user_id"),
        label=state_data.get("label"),
    )
    return RedirectResponse(f"{FRONTEND_URL}/dashboard?github=success")


async def process_github_user(access_token: str, user_id: str | None = None, label: str | None = None):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        user = (await client.get("https://api.github.com/user", headers=headers)).json()
        github_username = user["login"]
        starred = (
            await client.get(
                "https://api.github.com/user/starred?per_page=100",
                headers=headers,
            )
        ).json()
        repos = (
            await client.get(
                "https://api.github.com/user/repos?per_page=100&sort=pushed",
                headers=headers,
            )
        ).json()

    def clean(items):
        return [
            {
                "name": repo.get("name", ""),
                "description": repo.get("description") or "",
                "language": repo.get("language") or "",
                "topics": repo.get("topics", []),
            }
            for repo in items
            if isinstance(repo, dict)
        ]

    github_data = {
        "username": github_username,
        "starred": clean(starred),
        "repos": clean(repos),
    }
    vector, metadata = embed_github_data(github_data)

    resolved_user_id = user_id or github_username
    resolved_label = label or user.get("name") or github_username
    store_user_vector(
        user_id=resolved_user_id,
        source_vectors={"github": vector},
        metadata=metadata,
        seeded=False,
        label=resolved_label,
        github_username=github_username,
    )

    return {
        "status": "success",
        "user_id": resolved_user_id,
        "label": resolved_label,
        "github_username": github_username,
        "source": "github",
        "top_languages": metadata["github"]["top_languages"],
        "top_topics": metadata["github"]["top_topics"],
    }


@app.get("/spotify/login")
def spotify_login():
    query = urlencode(
        {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": SPOTIFY_REDIRECT_URI,
            "scope": SPOTIFY_SCOPES,
        }
    )
    return RedirectResponse(f"https://accounts.spotify.com/authorize?{query}")


@app.get("/spotify/callback")
async def spotify_callback(code: str):
    creds = base64.b64encode(f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()).decode()

    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
            },
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(400, f"Failed to get Spotify token: {token_data}")

    return await process_spotify_user(access_token)


async def process_spotify_user(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        profile = (await client.get("https://api.spotify.com/v1/me", headers=headers)).json()
        top_artists_res = (
            await client.get(
                "https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term",
                headers=headers,
            )
        ).json()
        top_tracks_res = (
            await client.get(
                "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term",
                headers=headers,
            )
        ).json()

    spotify_user_id = profile.get("id", "unknown")
    display_name = profile.get("display_name", spotify_user_id)

    spotify_data = {
        "username": spotify_user_id,
        "top_artists": [
            {"name": artist["name"], "genres": artist.get("genres", [])}
            for artist in top_artists_res.get("items", [])
        ],
        "top_tracks": [
            {
                "name": track["name"],
                "artist": track["artists"][0]["name"] if track.get("artists") else "",
            }
            for track in top_tracks_res.get("items", [])
        ],
        "top_genres": [],
    }

    vector, metadata = embed_spotify_data(spotify_data)
    if "spotify" not in metadata:
        metadata = {"spotify": metadata}

    store_user_vector(
        user_id=spotify_user_id,
        source_vectors={"spotify": vector},
        metadata=metadata,
        seeded=False,
        label=display_name,
    )

    spotify_meta = metadata.get("spotify", {})
    return {
        "status": "success",
        "user_id": spotify_user_id,
        "label": display_name,
        "source": "spotify",
        "top_artists": spotify_meta.get("top_artists", []),
        "top_genres": spotify_meta.get("top_genres", []),
    }


@app.get("/users/{user_id}")
def get_user(user_id: str):
    user = get_user_profile(user_id)
    if user is None:
        raise HTTPException(404, f"User {user_id} not found")
    return user


@app.get("/matches/{user_id}")
def get_matches(user_id: str, top_k: int = 5):
    matches = find_similar_users(user_id, top_k=top_k)
    if matches is None:
        raise HTTPException(404, f"User {user_id} not found")
    return {"user_id": user_id, "matches": matches}


class WeightedMatchRequest(BaseModel):
    user_id: str
    weights: dict
    top_k: int = 5


@app.post("/matches/weighted")
def get_weighted_matches(req: WeightedMatchRequest):
    matches = find_similar_weighted(req.user_id, req.weights, top_k=req.top_k)
    if matches is None:
        raise HTTPException(404, f"User {req.user_id} not found or has no source vectors")
    return {"user_id": req.user_id, "weights": req.weights, "matches": matches}


class SteamConnectRequest(BaseModel):
    user_id: str
    steam_identifier: str
    label: str | None = None


@app.post("/steam/connect")
async def connect_steam(req: SteamConnectRequest):
    steam_data = await fetch_steam_data(req.steam_identifier)

    if steam_data is None:
        raise HTTPException(400, "Could not fetch Steam data. Check your profile is public and the identifier is correct.")

    if not steam_data["games"]:
        raise HTTPException(400, "No games found. Make sure your Steam profile is set to public.")

    vector, metadata = embed_steam_data(steam_data)
    store_user_vector(
        user_id=req.user_id,
        source_vectors={"steam": vector},
        metadata=metadata,
        seeded=False,
        label=req.label or req.user_id,
    )

    steam_meta = metadata["steam"]
    return {
        "status": "success",
        "user_id": req.user_id,
        "label": req.label or req.user_id,
        "source": "steam",
        "total_games": steam_data["total_games"],
        "top_games": steam_meta["top_games"],
        "top_genres": steam_meta["top_genres"],
    }


@app.get("/umap")
def get_umap():
    points = compute_umap_3d()
    if not points:
        raise HTTPException(400, "Not enough users for UMAP (need at least 2)")
    return {"count": len(points), "points": points}


@app.get("/users")
def get_users():
    return {"users": list_all_users()}
