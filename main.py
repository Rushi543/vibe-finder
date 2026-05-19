import os
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from embedder import embed_github_data
from qdrant_store import store_user_vector, find_similar_users
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
GITHUB_REDIRECT_URI = "http://localhost:8000/auth/callback"


@app.get("/")
def root():
    return HTMLResponse("""
        <h2>Vibe Finder</h2>
        <a href="/auth/login">Connect GitHub</a>
    """)


@app.get("/auth/login")
def login():
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={GITHUB_REDIRECT_URI}"
        f"&scope=read:user,public_repo"
    )
    return RedirectResponse(github_auth_url)


@app.get("/auth/callback")
async def callback(code: str):
    # Exchange code for access token
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

    token_data = token_res.json()
    access_token = token_data.get("access_token")

    if not access_token:
        raise HTTPException(status_code=400, detail="Failed to get access token")

    # Fetch GitHub data and process
    result = await process_github_user(access_token)
    return result


async def process_github_user(access_token: str):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
    }

    async with httpx.AsyncClient() as client:
        # Get user profile
        user_res = await client.get("https://api.github.com/user", headers=headers)
        user = user_res.json()
        username = user["login"]

        # Get starred repos (up to 100)
        stars_res = await client.get(
            "https://api.github.com/user/starred?per_page=100",
            headers=headers,
        )
        starred = stars_res.json()

        # Get user's own repos
        repos_res = await client.get(
            "https://api.github.com/user/repos?per_page=100&sort=pushed",
            headers=headers,
        )
        repos = repos_res.json()

    # Build text corpus from GitHub data
    github_data = {
        "username": username,
        "starred": [
            {
                "name": r.get("name", ""),
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "topics": r.get("topics", []),
            }
            for r in starred
            if isinstance(r, dict)
        ],
        "repos": [
            {
                "name": r.get("name", ""),
                "description": r.get("description") or "",
                "language": r.get("language") or "",
                "topics": r.get("topics", []),
            }
            for r in repos
            if isinstance(r, dict)
        ],
    }

    # Embed and store
    vector, metadata = embed_github_data(github_data)
    store_user_vector(username, vector, metadata)

    return {
        "status": "success",
        "username": username,
        "repos_indexed": len(github_data["repos"]),
        "stars_indexed": len(github_data["starred"]),
        "top_languages": metadata["top_languages"],
        "top_topics": metadata["top_topics"],
    }


@app.get("/matches/{username}")
def get_matches(username: str, top_k: int = 5):
    matches = find_similar_users(username, top_k=top_k)
    if matches is None:
        raise HTTPException(status_code=404, detail=f"User {username} not found")
    return {"username": username, "matches": matches}


@app.get("/users")
def list_users():
    from qdrant_store import list_all_users
    return {"users": list_all_users()}

@app.get("/umap")
def get_umap():
    """
    Returns 3D UMAP coordinates for all users in Qdrant.
    Each entry: { username, x, y, z, top_languages, top_topics, seeded }
    """
    points = compute_umap_3d()
    if not points:
        raise HTTPException(status_code=400, detail="Not enough users to compute UMAP (need at least 2)")
    return {"count": len(points), "points": points}