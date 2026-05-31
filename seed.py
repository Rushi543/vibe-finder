import asyncio
import httpx
import sys
from embedder import embed_github_data
from anilist_fetcher import fetch_anilist_data
from anilist_embedder import embed_anilist_data
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


# Example AniList usernames to seed. Replace with real AniList usernames.
SEED_ANILIST_USERS = [
    # Site staff / well-known accounts
    "Xinil",        # AniList founder, huge list
    "Josh",         # co-founder
    "Taiga",        # popular user, diverse taste
 
    # Heavy watchers across different genres
    "Crispis",      # action/shonen heavy
    "Orangeish",    # slice of life / romance
    "Screech",      # mecha / sci-fi
    "Erifian",      # psychological / thriller
    "Yasaibatake",  # sports anime
    "Mystogan",     # fantasy / isekai
    "Nolan",        # horror / dark fantasy
    "Maora",        # music / arts anime
    "Kurasune",     # classic anime fan
    "Seraphius",    # long-running series
    "Dakadaka",     # comedy focused
    "Zhwan",        # mixed taste
    "Zii",          # shoujo / josei
    "Gavrial",      # mecha + sci-fi
    "Lyvarra",      # slice of life
    "Ryuk",         # death note / dark themes
    "Zeromus",      # RPG-adjacent anime
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


async def seed_anilist():
    """Seed users from AniList usernames using the AniList GraphQL API."""
    print(f"Seeding {len(SEED_ANILIST_USERS)} AniList users...\n")
    success = 0

    for i, username in enumerate(SEED_ANILIST_USERS):
        print(f"[{i+1}/{len(SEED_ANILIST_USERS)}] {username}...")
        try:
            data = await fetch_anilist_data(username)
        except Exception as e:
            print(f"  [error] {username}: {e}")
            data = None

        if not data:
            print(f"  [skip] {username} — no data")
            continue

        vector, metadata = embed_anilist_data(data)
        store_user_vector(
            user_id=username,
            source_vectors={"anilist": vector},
            metadata=metadata,
            seeded=True,
            label=username,
            github_username=None,
        )
        print(f"  ✓ top genres: {metadata.get('anilist', {}).get('top_genres', [])[:3]}")
        success += 1
        await asyncio.sleep(1.0)

    print(f"\nDone. {success}/{len(SEED_ANILIST_USERS)} seeded.")

if __name__ == "__main__":
    # Usage: `python seed.py [github|anilist|all]`
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else "github"
    if arg == "anilist":
        asyncio.run(seed_anilist())
    elif arg == "all":
        asyncio.run(seed())
        asyncio.run(seed_anilist())
    else:
        asyncio.run(seed())
