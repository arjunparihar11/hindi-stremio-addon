import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime

app = FastAPI()

# Enable CORS for Stremio integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MANIFEST = {
    "id": "community.dynamicindiancatalogs",
    "version": "1.1.0",
    "name": "Hindi Media Hub",
    "description": "Latest and upcoming catalogs for Hindi movies and series.",
    "resources": ["catalog"],
    "types": ["movie", "series"],
    "idPrefixes": ["tmdb"],
    "catalogs": [
        {"type": "movie", "id": "latest_hindi_movies", "name": "Latest Hindi Movies"},
        {"type": "series", "id": "latest_hindi_shows", "name": "Latest Hindi Shows"},
        {"type": "movie", "id": "upcoming_hindi_movies", "name": "Upcoming Hindi Movies"},
        {"type": "series", "id": "upcoming_hindi_shows", "name": "Upcoming Hindi Shows"}
    ]
}

# Pulls token from Render environment variables first, falls back to hardcoded string
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "5bac60b56fcf01fd5cdca7d856416355")
BASE_URL = "https://api.themoviedb.org/3"

def fetch_hindi_media(media_type="movie", status="latest"):
    endpoint = f"{BASE_URL}/discover/{media_type}"
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    params = {
        "api_key": TMDB_API_KEY,
        "with_original_language": "hi",
        "page": 1
    }
    
    if media_type == "movie":
        params["sort_by"] = "primary_release_date.desc" if status == "latest" else "primary_release_date.asc"
        if status == "latest":
            params["primary_release_date.lte"] = today_str
        else:
            params["primary_release_date.gte"] = today_str
    else:
        params["sort_by"] = "first_air_date.desc" if status == "latest" else "first_air_date.asc"
        if status == "latest":
            params["first_air_date.lte"] = today_str
        else:
            params["first_air_date.gte"] = today_str

    response = requests.get(endpoint, params=params)
    if response.status_code != 200:
        return []
        
    results = response.json().get("results", [])
    metas = []
    
    for item in results:
        title = item.get("title") if media_type == "movie" else item.get("name")
        release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
        year = release_date.split("-")[0] if release_date else "TBA"
        poster_path = item.get("poster_path")
        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://via.placeholder.com/500x750"
        
        metas.append({
            "id": f"tmdb:{item.get('id')}", 
            "type": "movie" if media_type == "movie" else "series",
            "name": title,
            "poster": poster_url,
            "releaseInfo": year,
            "description": f"Release Date: {release_date or 'TBA'}\n\n{item.get('overview', '')}"
        })
        
    return metas

@app.get("/manifest.json")
async def get_manifest():
    return MANIFEST

@app.get("/catalog/{content_type}/{catalog_id}.json")
async def get_catalog(content_type: str, catalog_id: str):
    if catalog_id == "latest_hindi_movies" and content_type == "movie":
        return {"metas": fetch_hindi_media("movie", "latest")}
    elif catalog_id == "latest_hindi_shows" and content_type == "series":
        return {"metas": fetch_hindi_media("tv", "latest")}
    elif catalog_id == "upcoming_hindi_movies" and content_type == "movie":
        return {"metas": fetch_hindi_media("movie", "upcoming")}
    elif catalog_id == "upcoming_hindi_shows" and content_type == "series":
        return {"metas": fetch_hindi_media("tv", "upcoming")}
    return {"metas": []}
