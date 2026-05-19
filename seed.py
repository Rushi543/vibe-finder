import asyncio
import httpx
from embedder import embed_github_data
from qdrant_store import store_user_vector
from dotenv import load_dotenv
from qdrant_store import get_point_id
load_dotenv()

# Diverse set of well-known GitHub users across different domains
# Mix of: systems, ML, web, game dev, data science, security, mobile
SEED_USERS = [
    # Systems / Low-level
    "torvalds",       # Linux
    "antirez",        # Redis
    "graydon",        # Rust creator
    "mitchellh",      # Vagrant, Go tools
    "jart",           # Cosmopolitan libc

    # ML / AI
    "karpathy",       # nanoGPT, llm.c
    "fchollet",       # Keras
    "tiangolo",       # FastAPI (also MLish)
    "huggingface",    # transformers
    "lucidrains",     # ML research implementations

    # Web / Frontend
    "tj",             # Express.js
    "sindresorhus",   # Massive JS ecosystem
    "gaearon",        # React core
    "yyx990803",      # Vue.js
    "Rich-Harris",    # Svelte

    # Data / Python
    "wesmckinney",    # pandas
    "jakevdp",        # Python data science
    "mwaskom",        # seaborn
    "pypa",           # pip, packaging
    "coleifer",       # peewee, misc tools

    # Security / Infra
    "taviso",         # security research
    "hdm",            # metasploit
    "nicowillis",     # infra tooling
    "kelseyhightower",# Kubernetes
    "jessfraz",       # containers, security

    # Game dev / Creative
    "id-Software",    # Quake source
    "aras-p",         # Unity
    "kripken",        # emscripten
    "bulletphysics",  # Bullet physics

    # Mobile
    "JohnCoates",     # iOS tools
    "nicklockwood",   # iOS libs
    "square",         # Android/iOS SDKs
]


async def fetch_public_github_data(username: str, client: httpx.AsyncClient) -> dict | None:
    """Fetch public GitHub data for a user — no auth token needed."""
    headers = {"Accept": "application/vnd.github+json"}

    try:
        # Get starred repos
        stars_res = await client.get(
            f"https://api.github.com/users/{username}/starred?per_page=100",
            headers=headers,
            timeout=10.0,
        )
        if stars_res.status_code == 404:
            print(f"  [skip] {username} not found")
            return None
        if stars_res.status_code == 403:
            print(f"  [skip] {username} rate limited — add a GitHub token to .env")
            return None

        starred = stars_res.json() if stars_res.status_code == 200 else []

        # Get their own repos
        repos_res = await client.get(
            f"https://api.github.com/users/{username}/repos?per_page=100&sort=pushed",
            headers=headers,
            timeout=10.0,
        )
        repos = repos_res.json() if repos_res.status_code == 200 else []

        return {
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

    except Exception as e:
        print(f"  [error] {username}: {e}")
        return None


def store_seeded_user(username: str, vector: list[float], metadata: dict):
    """Same as store_user_vector but marks the user as seeded."""
    from qdrant_store import ensure_collection, client, COLLECTION_NAME
    from qdrant_client.models import PointStruct

    ensure_collection()
    point_id = get_point_id(username)

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "username": username,
                    "top_languages": metadata.get("top_languages", []),
                    "top_topics": metadata.get("top_topics", []),
                    "total_items": metadata.get("total_items", 0),
                    "source": "github",
                    "seeded": True,   # <-- flag for frontend styling
                },
            )
        ],
    )


async def seed():
    print(f"Seeding {len(SEED_USERS)} users into Qdrant...\n")
    success = 0
    failed = 0

    # Respect GitHub's unauthenticated rate limit (60 req/hour)
    # We make 2 requests per user, so max ~30 users unauthenticated
    # Add GITHUB_TOKEN to .env for higher limits (5000 req/hour)
    import os
    token = os.getenv("GITHUB_TOKEN")
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        print("Using GitHub token — higher rate limits active\n")
    else:
        print("No GITHUB_TOKEN found — unauthenticated (60 req/hour limit)")
        print("Add GITHUB_TOKEN=your_pat to .env for full seed\n")

    async with httpx.AsyncClient(headers=headers) as client:
        for i, username in enumerate(SEED_USERS):
            print(f"[{i+1}/{len(SEED_USERS)}] {username}...")

            data = await fetch_public_github_data(username, client)
            if data is None:
                failed += 1
                continue

            vector, metadata = embed_github_data(data)
            store_seeded_user(username, vector, metadata)

            print(f"  ✓ stored | langs: {metadata['top_languages'][:3]} | topics: {metadata['top_topics'][:3]}")
            success += 1

            # Small delay to avoid hammering the API
            await asyncio.sleep(1.5)

    print(f"\nDone. {success} seeded, {failed} failed.")


if __name__ == "__main__":
    asyncio.run(seed())