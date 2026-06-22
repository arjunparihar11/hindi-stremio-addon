import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MANIFEST = {
    "id": "community.dynamicindiancatalogs",
    "version": "1.3.0",
    "name": "Hindi Media Hub (Smart Posters)",
    "description": "Latest and upcoming Hindi catalogs featuring RPDB dynamic posters with ratings and tags.",
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

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "your_tmdb_api_key_here")
# Add your RPDB API Key here or set it as a Render Environment Variable
RPDB_API_KEY = os.environ.get("RPDB_API_KEY", "your_rpdb_api_key_here") 

BASE_URL = "https://api.themoviedb.org/3"

def fetch_hindi_media(media_type="movie", status="latest"):
    endpoint = f"{BASE_URL}/discover/{media_type}"
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    params = {
        "api_key": TMDB_API_KEY,
        "with_original_language": "hi"
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

    metas = []
    
    for page in range(1, 6):
        params["page"] = page
        response = requests.get(endpoint, params=params)
        
        if response.status_code != 200:
            break
            
        results = response.json().get("results", [])
        if not results:
            break
            
        for item in results:
            tmdb_id = item.get("id")
            title = item.get("title") if media_type == "movie" else item.get("name")
            release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
            year = release_date.split("-")[0] if release_date else "TBA"
            
            # --- RPDB Poster Integration ---
            # If an RPDB key is provided, route the image through btttr.cc/RPDB
            if RPDB_API_KEY and RPDB_API_KEY != "your_rpdb_api_key_here":
                # Patterns: poster-default includes scores, genres, and basic tags.
                # Use 'tmdb' mapping directly so we don't have to make extra heavy API calls for IMDb IDs.
                poster_url = f"https://api.rpdb.to/v1/{RPDB_API_KEY}/tmdb/poster-default/{tmdb_id}.jpg"
            else:
                # Fallback to normal clean TMDB posters if no key is present
                poster_path = item.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://via.placeholder.com/500x750"
            
            metas.append({
                "id": f"tmdb:{tmdb_id}", 
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
