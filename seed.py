import asyncio
import httpx
from embedder import embed_github_data
from qdrant_store import store_user_vector
from dotenv import load_dotenv
from qdrant_store import get_point_id
import os

load_dotenv()

SEED_USERS = [
    # Systems / Low-level
    "torvalds", "antirez", "mitchellh", "jart",
    # ML / AI
    "karpathy", "fchollet", "lucidrains","tiangolo", "huggingface",
    # Web / Frontend
    "tj", "sindresorhus", "gaearon", "yyx990803", "Rich-Harris",
    # Data / Python
    "wesmckinney", "jakevdp", "mwaskom", "coleifer",
    # Security / Infra
    "taviso", "kelseyhightower", "jessfraz",
    # Game dev / Creative
    "aras-p", "kripken",
    # Mobile
    "nicklockwood","JohnCoates",
]


async def fetch_public_github_data(username: str, client: httpx.AsyncClient):
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        stars_res = await client.get(
            f"https://api.github.com/users/{username}/starred?per_page=100",
            headers=headers, timeout=10.0,
        )
        if stars_res.status_code in (404, 403):
            print(f"  [skip] {username} — {stars_res.status_code}")
            return None
        starred = stars_res.json() if stars_res.status_code == 200 else []

        repos_res = await client.get(
            f"https://api.github.com/users/{username}/repos?per_page=100&sort=pushed",
            headers=headers, timeout=10.0,
        )
        repos = repos_res.json() if repos_res.status_code == 200 else []

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

        return {"username": username, "starred": clean(starred), "repos": clean(repos)}

    except Exception as e:
        print(f"  [error] {username}: {e}")
        return None


async def seed():
    print(f"Seeding {len(SEED_USERS)} users...\n")
    success = 0

    async with httpx.AsyncClient() as client:
        for i, username in enumerate(SEED_USERS):
            print(f"[{i+1}/{len(SEED_USERS)}] {username}...")
            data = await fetch_public_github_data(username, client)
            if data is None:
                continue

            vector, metadata = embed_github_data(data)
            store_user_vector(
                user_id=username,
                source_vectors={"github": vector},
                metadata=metadata,
                seeded=True,
                label=username,
                github_username=username,
            )
            print(f"  ✓ langs: {metadata['github']['top_languages'][:3]}")
            success += 1
            await asyncio.sleep(1.5)

    print(f"\nDone. {success}/{len(SEED_USERS)} seeded.")


if __name__ == "__main__":
    asyncio.run(seed())
