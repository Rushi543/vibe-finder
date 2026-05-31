# VibeFinder

VibeFinder is a social matching app built for the Qdrant Vector Space Hackathon. It lets a user sign in, connect identity and interest sources, turn them into vectors, and explore similar profiles in an interactive 3D scene.

Today the app supports:

- `GitHub` for repos, stars, languages, and topics
- `Steam` for games, playtime, and genres
- `AniList` for anime favorites, genres, and related taste signals

## What the app does

After signing in with Supabase, a user can connect one or more sources from the dashboard. Each source is embedded separately, merged into a single stored profile in Qdrant, and then surfaced in the explore experience.

The explore page currently includes:

- A `Space` view for the full UMAP map of profiles
- A `Galaxy` view where the selected user becomes the sun and nearest matches orbit around them
- Live match explanations shown in the side panel
- Reweighting sliders for a user with multiple connected sources
- Hover tooltips, match cards, similarity bars, and seeded-profile visibility toggles

The galaxy view now includes:

- Similarity-aware orbit spacing
- Animated orbiting planets
- A pulsing sun
- Bloom/glow postprocessing
- Source-based planet coloring

## How it works

1. Each source is fetched and embedded independently.
2. Source vectors are merged into a single profile vector.
3. The profile is stored in Qdrant with useful metadata for the UI.
4. Match queries return nearest neighbors plus short natural-language explanations.
5. UMAP reduces the stored vectors into 3D coordinates for the map view.

## Stack

- Frontend: `React`, `Vite`, `React Router`, `React Three Fiber`, `@react-three/drei`, `@react-three/postprocessing`
- Backend: `FastAPI`, `Python`
- Vector store: `Qdrant`
- Embeddings: `sentence-transformers`
- Auth: `Supabase` auth in the frontend, with Google sign-in used in the current UI
- Visualization: `UMAP` to 3D

## Project structure

```text
.
├─ frontend/                 # React app
├─ main.py                   # FastAPI app
├─ qdrant_store.py           # vector storage + similarity search
├─ match_explainer.py        # natural-language match explanations
├─ seed.py                   # seeded demo profiles
└─ umap_compute.py           # 3D projection for explore view
```

## Local setup

### 1. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy and fill:

- root `.env` from `.env.example`
- `frontend/.env`

At minimum you will need values for your API URL, Supabase project, and any source integrations you want to enable.

### 3. Run the backend

```bash
uvicorn main:app --reload --port 8000
```

### 4. Run the frontend

```bash
cd frontend
npm install
npm run dev
```

## Seeding demo profiles

```bash
python seed.py
```

This adds seeded comparison profiles so the explore scene is more interesting before many real users connect data.

## API notes

The current frontend uses these main backend endpoints:

- `GET /users/{user_id}`
- `GET /umap`
- `GET /matches/{user_id}`
- `POST /matches/weighted`
- `GET /auth/github/start`
- `POST /steam/connect`
- `POST /anilist/connect`

## Current caveats

- The frontend production build still reports a large chunk-size warning from Vite.
- There are a few legacy backend pieces still present in the repo, such as Spotify-related code, even though the current UI focuses on GitHub, Steam, and AniList.
