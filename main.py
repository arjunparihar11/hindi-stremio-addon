import os
import requests
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MANIFEST = {
    "id": "community.dynamicindiancatalogs",
    "version": "1.6.0",
    "name": "Hindi Media Hub (btttr.cc)",
    "description": "Latest/Upcoming Hindi catalogs using btttr.cc query strings for ratings.",
    "resources": ["catalog"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt", "tmdb"],
    "catalogs": [
        {"type": "movie", "id": "latest_hindi_movies", "name": "Latest Hindi Movies"},
        {"type": "series", "id": "latest_hindi_shows", "name": "Latest Hindi Shows"},
        {"type": "movie", "id": "upcoming_hindi_movies", "name": "Upcoming Hindi Movies"},
        {"type": "series", "id": "upcoming_hindi_shows", "name": "Upcoming Hindi Shows"}
    ]
}

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "your_tmdb_api_key_here")
BASE_URL = "https://api.themoviedb.org/3"

def get_imdb_id(tmdb_id: str, media_type: str) -> str:
    type_path = "movie" if media_type == "movie" else "tv"
    url = f"{BASE_URL}/{type_path}/{tmdb_id}/external_ids"
    params = {"api_key": TMDB_API_KEY}
    try:
        res = requests.get(url, params=params, timeout=3)
        if res.status_code == 200:
            return res.json().get("imdb_id")
    except Exception:
        pass
    return None

def search_tmdb_fallback(title: str, media_type: str):
    search_type = "movie" if media_type == "movie" else "tv"
    url = f"{BASE_URL}/search/{search_type}"
    params = {"api_key": TMDB_API_KEY, "query": title, "language": "hi"}
    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code == 200 and res.json().get("results"):
            for match in res.json()["results"]:
                if match.get("original_language") == "hi":
                    return match
            return res.json()["results"][0]
    except Exception:
        pass
    return None

def scrape_binged_premiere_titles():
    titles = []
    url = "https://www.binged.com/streaming-premiere-dates/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for element in soup.find_all(['h3', 'div'], class_=['back_title', 'title']):
                clean_title = element.get_text(strip=True)
                if clean_title:
                    titles.append(clean_title)
    except Exception:
        pass
    return titles

def fetch_hindi_media(media_type="movie", status="latest"):
    endpoint = f"{BASE_URL}/discover/{media_type}"
    today_str = datetime.today().strftime('%Y-%m-%d')
    
    params = {
        "api_key": TMDB_API_KEY,
        "with_original_language": "hi"
    }
    
    if media_type == "movie":
        params["sort_by"] = "primary_release_date.desc" if status == "latest" else "primary_release_date.asc"
        params["primary_release_date.lte" if status == "latest" else "primary_release_date.gte"] = today_str
    else:
        params["sort_by"] = "first_air_date.desc" if status == "latest" else "first_air_date.asc"
        params["first_air_date.lte" if status == "latest" else "first_air_date.gte"] = today_str

    merged_catalog = {}

    # Phase 1: Ingest TMDB discover list
    for page in range(1, 6):
        params["page"] = page
        try:
            response = requests.get(endpoint, params=params, timeout=5)
            if response.status_code != 200:
                break
            results = response.json().get("results", [])
            if not results:
                break
                
            for item in results:
                tmdb_id = str(item.get("id"))
                if tmdb_id not in merged_catalog:
                    imdb_id = get_imdb_id(tmdb_id, media_type)
                    
                    # Apply your explicit btttr.cc structural link matching configuration
                    if imdb_id:
                        poster_url = f"https://btttr.cc/poster-q/imdb/poster-default/{imdb_id}.jpg?rs=RT"
                        stremio_id = imdb_id
                    else:
                        poster_path = item.get("poster_path")
                        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://via.placeholder.com/500x750"
                        stremio_id = f"tmdb:{tmdb_id}"

                    title = item.get("title") if media_type == "movie" else item.get("name")
                    release_date = item.get("release_date") if media_type == "movie" else item.get("first_air_date")
                    year = release_date.split("-")[0] if release_date else "TBA"

                    merged_catalog[tmdb_id] = {
                        "id": stremio_id, 
                        "type": "movie" if media_type == "movie" else "series",
                        "name": title,
                        "poster": poster_url,
                        "releaseInfo": year,
                        "description": f"Release Date: {release_date or 'TBA'}\n\n{item.get('overview', '')}",
                        "timestamp": release_date or "0000-00-00"
                    }
        except Exception:
            break

    # Phase 2: Ingest Binged Scraped Titles
    scraped_titles = scrape_binged_premiere_titles()
    for raw_title in scraped_titles:
        tmdb_item = search_tmdb_fallback(raw_title, media_type)
        if tmdb_item:
            tmdb_id = str(tmdb_item.get("id"))
            if tmdb_id not in merged_catalog:
                release_date = tmdb_item.get("release_date") if media_type == "movie" else tmdb_item.get("first_air_date")
                is_past = release_date and release_date <= today_str
                
                if (status == "latest" and is_past) or (status == "upcoming" and not is_past):
                    imdb_id = get_imdb_id(tmdb_id, media_type)
                    
                    if imdb_id:
                        poster_url = f"https://btttr.cc/poster-q/imdb/poster-default/{imdb_id}.jpg?rs=RT"
                        stremio_id = imdb_id
                    else:
                        poster_url = f"https://image.tmdb.org/t/p/w500{tmdb_item.get('poster_path')}" if tmdb_item.get('poster_path') else "https://via.placeholder.com/500x750"
                        stremio_id = f"tmdb:{tmdb_id}"

                    title = tmdb_item.get("title") if media_type == "movie" else tmdb_item.get("name")
                    year = release_date.split("-")[0] if release_date else "TBA"
                    
                    merged_catalog[tmdb_id] = {
                        "id": stremio_id,
                        "type": "movie" if media_type == "movie" else "series",
                        "name": title,
                        "poster": poster_url,
                        "releaseInfo": year,
                        "description": f"[Via Binged] Release Date: {release_date or 'TBA'}\n\n{tmdb_item.get('overview', '')}",
                        "timestamp": release_date or "0000-00-00"
                    }

    final_list = list(merged_catalog.values())
    is_reverse = (status == "latest")
    final_list.sort(key=lambda x: x["timestamp"], reverse=is_reverse)
    
    return [ {k: v for k, v in item.items() if k != "timestamp"} for item in final_list[:100] ]

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
