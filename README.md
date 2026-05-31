# VibeFinder

VibeFinder maps people as vectors. Connect your GitHub, Steam, and AniList accounts and find 
developers who share your technical identity, gaming taste, and anime interests — all at once, 
or reweighted however you like.

Built for the Qdrant Vector Space Hackathon.

## Live demo

https://vibe-finder-eta.vercel.app

## How it works

Each connected source is embedded independently:

- **GitHub** — repo descriptions, starred projects, languages and topics → sentence-transformers
- **Steam** — game names, genres, playtime-weighted → sentence-transformers  
- **AniList** — genres, tags, favourites, watch-time-weighted → sentence-transformers

The three vectors are fused into a single weighted personality vector and stored in Qdrant. 
UMAP reduces the full collection to 3D coordinates for spatial exploration.

The key interaction: sliders reweight the fusion vector live and re-query Qdrant in real time — 
so you can find your coding twin, your gaming twin, or your anime twin from the same profile.

## Stack

- **Frontend:** React + Vite + React Three Fiber
- **Backend:** FastAPI + Python
- **Vector DB:** Qdrant Cloud
- **Embeddings:** sentence-transformers (`all-MiniLM-L6-v2`)
- **Dimensionality reduction:** UMAP → 3D
- **Auth:** Supabase (Google OAuth)

## Run locally

```bash
# Backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend-app
npm install
npm run dev
```

Copy `.env.example` to `.env` in both the root and `frontend-app/` and fill in your keys.

## Seeding

```bash
python seed.py          # seeds GitHub profiles
```