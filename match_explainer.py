import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE = Path(__file__).with_name('match_explanations_cache.json')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')


def _load_cache() -> dict[str, str]:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding='utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding='utf-8')


def _cache_key(user_id: str, match_id: str) -> str:
    return '::'.join(sorted([user_id, match_id]))


def _clean_list(values: list[Any]) -> list[str]:
    return [str(value).strip() for value in values if isinstance(value, str) and value.strip()]


def _list_intersection(first: list[str], second: list[str]) -> list[str]:
    normalized = {item.lower(): item for item in _clean_list(second)}
    return [item for item in _clean_list(first) if item.lower() in normalized]


def _humanize_list(values: list[str], limit: int = 3) -> str:
    if not values:
        return ''
    slice_values = values[:limit]
    if len(slice_values) == 1:
        return slice_values[0]
    if len(slice_values) == 2:
        return f"{slice_values[0]} and {slice_values[1]}"
    return f"{', '.join(slice_values[:-1])}, and {slice_values[-1]}"


def _build_prompt(match_label: str, overlaps: dict[str, list[str]]) -> str:
    lines = [
        'You are a concise similarity explainer for a pair of matched user profiles.',
        'Use only the overlap data provided, and do not invent or infer anything beyond the lists below.',
        f'Write a clear, positive explanation in 2–4 sentences starting with "You and {match_label}".',
        'Use complete English sentences and do not produce sentence fragments.',
        'If there are no overlaps, say the profile similarity is based on their combined interests and vector similarity.',
        '\nOverlap data provided:',
    ]

    if overlaps['languages']:
        lines.append(f"- Common GitHub languages: {', '.join(overlaps['languages'])}")
    if overlaps['topics']:
        lines.append(f"- Common GitHub topics or technologies: {', '.join(overlaps['topics'])}")
    if overlaps['games']:
        lines.append(f"- Common Steam games: {', '.join(overlaps['games'])}")
    if overlaps['genres']:
        lines.append(f"- Common Steam / AniList genres: {', '.join(overlaps['genres'])}")
    if overlaps['anime']:
        lines.append(f"- Common AniList anime or favorites: {', '.join(overlaps['anime'])}")

    lines.append('\nWrite a single concise explanation.')
    return '\n'.join(lines)


def _build_overlap_data(user_profile: dict[str, Any], match_profile: dict[str, Any]) -> dict[str, list[str]]:
    common_languages = _list_intersection(user_profile.get('top_languages', []), match_profile.get('top_languages', []))
    common_topics = _list_intersection(user_profile.get('top_topics', []), match_profile.get('top_topics', []))
    common_games = _list_intersection(user_profile.get('top_games', []), match_profile.get('top_games', []))
    common_genres = _list_intersection(user_profile.get('top_genres', []), match_profile.get('top_genres', []))

    user_anime = _clean_list(user_profile.get('top_anime', []) or []) + _clean_list(user_profile.get('top_favorites', []) or [])
    match_anime_set = set(_clean_list(match_profile.get('top_anime', []) or []) + _clean_list(match_profile.get('top_favorites', []) or []))
    common_anime = [anime for anime in user_anime if anime in match_anime_set]

    return {
        'languages': common_languages,
        'topics': common_topics,
        'games': common_games,
        'genres': common_genres,
        'anime': common_anime,
    }


def _deterministic_explanation(match_label: str, overlaps: dict[str, list[str]]) -> str:
    pieces = []

    if overlaps['languages']:
        pieces.append(f"both of you work with { _humanize_list(overlaps['languages']) }")
    if overlaps['topics']:
        pieces.append(f"share interests in { _humanize_list(overlaps['topics']) }")
    if overlaps['games']:
        pieces.append(f"you both enjoy { _humanize_list(overlaps['games']) }")
    if overlaps['genres']:
        pieces.append(f"prefer { _humanize_list(overlaps['genres']) } genres")
    if overlaps['anime']:
        pieces.append(f"watch { _humanize_list(overlaps['anime']) }")

    if not pieces:
        return (
            f"You and {match_label} were matched by the profile similarity engine based on your combined GitHub, Steam, and AniList embeddings, even though there are no strong explicit list overlaps to name here."
        )

    summary = ''
    if len(pieces) == 1:
        summary = pieces[0]
    elif len(pieces) == 2:
        summary = f"{pieces[0]} and {pieces[1]}"
    else:
        summary = f"{', '.join(pieces[:2])}, and {pieces[2]}"

    explanation = f"You and {match_label} are a strong match because {summary}."
    return explanation


def _generate_with_chat_api(prompt: str, *, api_key: str, model: str, base_url: str) -> str | None:
    if not api_key:
        return None

    try:
        response = httpx.post(
            f'{base_url}/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': model,
                'messages': [
                    {
                        'role': 'system',
                        'content': 'You are a concise match explainer that uses only the overlap information supplied. Write natural, complete sentences in 2-4 sentences. Do not invent details or output fragments.',
                    },
                    {'role': 'user', 'content': prompt},
                ],
                'temperature': 0.25,
                'max_tokens': 120,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        payload = response.json()
        text = payload['choices'][0]['message']['content'].strip()
        return text or None
    except Exception:
        return None


def _generate_with_llm(prompt: str) -> str | None:
    # Prefer Groq when configured because this project currently stores a Groq key.
    if GROQ_API_KEY:
        return _generate_with_chat_api(
            prompt,
            api_key=GROQ_API_KEY,
            model=GROQ_MODEL,
            base_url='https://api.groq.com/openai/v1',
        )

    if OPENAI_API_KEY:
        return _generate_with_chat_api(
            prompt,
            api_key=OPENAI_API_KEY,
            model=OPENAI_MODEL,
            base_url='https://api.openai.com/v1',
        )

    return None


def get_match_explanation(user_profile: dict[str, Any], match_profile: dict[str, Any]) -> str:
    user_id = user_profile.get('user_id') or user_profile.get('username') or ''
    match_id = match_profile.get('user_id') or match_profile.get('username') or ''
    cache_key = _cache_key(user_id, match_id)
    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]

    overlaps = _build_overlap_data(user_profile, match_profile)
    prompt = _build_prompt(match_profile.get('label') or match_id, overlaps)
    explanation = _generate_with_llm(prompt) or _deterministic_explanation(match_profile.get('label') or match_id, overlaps)
    cache[cache_key] = explanation
    _save_cache(cache)
    return explanation
