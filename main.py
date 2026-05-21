import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from embedder import embed_github_data
from spotify_embedder import embed_spotify_data
from qdrant_store import store_user_vector, find_similar_users, find_similar_weighted, list_all_users
from umap_compute import compute_umap_3d

load_dotenv()

app = FastAPI(title="Vibe Finder")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GITHUB_CLIENT_ID     = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI  = "http://localhost:8000/auth/callback"

SPOTIFY_CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/spotify/callback")
SPOTIFY_SCOPES        = "user-top-read user-read-private"


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return HTMLResponse("""
        <h2>Vibe Finder</h2>
        <p><a href="/auth/login">Connect GitHub</a></p>
        <p><a href="/spotify/login">Connect Spotify</a></p>
    """)


# ─── GitHub OAuth ─────────────────────────────────────────────────────────────

@app.get("/auth/login")
def github_login():
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope=read:user,public_repo"
    )
    return RedirectResponse(url)


@app.get("/auth/callback")
async def github_callback(code: str):
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
    return await process_github_user(token)


async def process_github_user(access_token: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }
    async with httpx.AsyncClient() as client:
        user = (await client.get("https://api.github.com/user", headers=headers)).json()
        username = user["login"]
        starred = (await client.get(
            "https://api.github.com/user/starred?per_page=100", headers=headers
        )).json()
        repos = (await client.get(
            "https://api.github.com/user/repos?per_page=100&sort=pushed", headers=headers
        )).json()

    def clean(items):
        return [
            {
                "name": r.get("name", ""),
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "topics": r.get("topics", []),
            }
            for r in items if isinstance(r, dict)
        ]

    github_data = {"username": username, "starred": clean(starred), "repos": clean(repos)}
    vector, metadata = embed_github_data(github_data)

    store_user_vector(
        username=username,
        source_vectors={"github": vector},
        metadata=metadata,
        seeded=False,
    )

    return {
        "status": "success",
        "username": username,
        "source": "github",
        "top_languages": metadata["github"]["top_languages"],
        "top_topics": metadata["github"]["top_topics"],
    }


# ─── Spotify OAuth ────────────────────────────────────────────────────────────

@app.get("/spotify/login")
def spotify_login():
    url = (
        f"https://accounts.spotify.com/authorize"
        f"?client_id={SPOTIFY_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={SPOTIFY_REDIRECT_URI}"
        f"&scope={SPOTIFY_SCOPES.replace(' ', '%20')}"
    )
    return RedirectResponse(url)


@app.get("/spotify/callback")
async def spotify_callback(code: str):
    import base64
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
        top_artists_res = (await client.get(
            "https://api.spotify.com/v1/me/top/artists?limit=50&time_range=medium_term",
            headers=headers,
        )).json()
        top_tracks_res = (await client.get(
            "https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=medium_term",
            headers=headers,
        )).json()

    username = profile.get("id", "unknown")
    display_name = profile.get("display_name", username)

    spotify_data = {
        "username": username,
        "top_artists": [
            {"name": a["name"], "genres": a.get("genres", [])}
            for a in top_artists_res.get("items", [])
        ],
        "top_tracks": [
            {"name": t["name"], "artist": t["artists"][0]["name"] if t.get("artists") else ""}
            for t in top_tracks_res.get("items", [])
        ],
        "top_genres": [],  # will be computed in embedder
    }

    vector, metadata = embed_spotify_data(spotify_data)

    # embed_spotify_data returns flat metadata (not nested under 'spotify').
    # Normalize so metadata is always nested under the 'spotify' key.
    if "spotify" not in metadata:
        metadata = {"spotify": metadata}

    # Use Spotify display name as the key — or ask user to link to their GitHub username
    store_user_vector(
        username=username,
        source_vectors={"spotify": vector},
        metadata=metadata,
        seeded=False,
    )

    spotify_meta = metadata.get("spotify", {})
    return {
        "status": "success",
        "username": username,
        "display_name": display_name,
        "source": "spotify",
        "top_artists": spotify_meta.get("top_artists", []),
        "top_genres": spotify_meta.get("top_genres", []),
    }


# ─── Query endpoints ──────────────────────────────────────────────────────────

@app.get("/matches/{username}")
def get_matches(username: str, top_k: int = 5):
    matches = find_similar_users(username, top_k=top_k)
    if matches is None:
        raise HTTPException(404, f"User {username} not found")
    return {"username": username, "matches": matches}


class WeightedMatchRequest(BaseModel):
    username: str
    weights: dict  # e.g. { "github": 0.7, "spotify": 0.3 }
    top_k: int = 5


@app.post("/matches/weighted")
def get_weighted_matches(req: WeightedMatchRequest):
    matches = find_similar_weighted(req.username, req.weights, top_k=req.top_k)
    if matches is None:
        raise HTTPException(404, f"User {req.username} not found or has no source vectors")
    return {"username": req.username, "weights": req.weights, "matches": matches}


@app.get("/umap")
def get_umap():
    points = compute_umap_3d()
    if not points:
        raise HTTPException(400, "Not enough users for UMAP (need at least 2)")
    return {"count": len(points), "points": points}


@app.get("/users")
def get_users():
    return {"users": list_all_users()}
