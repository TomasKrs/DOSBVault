import requests
import time
from datetime import datetime

class IGDBClient:
    BASE_URL = "https://api.igdb.com/v4"
    AUTH_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiry = 0

    def _authenticate(self):
        if self.access_token and time.time() < self.token_expiry:
            return

        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials"
        }
        try:
            response = requests.post(self.AUTH_URL, params=params)
            response.raise_for_status()
            data = response.json()
            self.access_token = data["access_token"]
            self.token_expiry = time.time() + data["expires_in"] - 60 # Buffer
        except Exception as e:
            raise Exception(f"IGDB Authentication failed: {e}")

    def search_game(self, query):
        self._authenticate()
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        # Search for games, get cover, release dates, companies, summary, rating
        # We filter for platform 13 (PC DOS) if possible, but many DOS games are just listed as PC (6)
        # Platform 13 is "PC DOS"
        body = f"""
        search "{query}";
        fields name, summary, first_release_date, total_rating, cover.url, involved_companies.company.name, involved_companies.developer, involved_companies.publisher, platforms.name, genres.name;
        where platforms = (13, 6); 
        limit 10;
        """
        
        try:
            response = requests.post(f"{self.BASE_URL}/games", headers=headers, data=body)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"IGDB Search failed: {e}")

    def get_cover_image(self, url):
        if not url: return None
        # IGDB urls often start with //
        if url.startswith("//"): url = "https:" + url
        # Replace thumb with cover_big or 720p
        url = url.replace("t_thumb", "t_cover_big")
        
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            return response.content
        except Exception:
            return None
