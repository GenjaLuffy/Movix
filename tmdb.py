import requests

API_KEY = "YOUR_REAL_TMDB_KEY"

BASE_URL = "https://api.themoviedb.org/3/movie/"
IMG_BASE = "https://image.tmdb.org/t/p/w500"


def get_movie_details(movie_id):
    try:
        url = f"{BASE_URL}{movie_id}?api_key={API_KEY}"
        response = requests.get(url, timeout=5)

        print("TMDB STATUS:", response.status_code)
        print("TMDB RESPONSE:", response.text[:200])

        if response.status_code != 200:
            return None

        return response.json()

    except Exception as e:
        print("TMDB ERROR:", e)
        return None


def get_poster_url(movie_id):
    """Fetch just the poster URL for a given TMDB movie id, or None."""
    data = get_movie_details(movie_id)
    if not data or not data.get("poster_path"):
        return None
    return f"{IMG_BASE}{data['poster_path']}"