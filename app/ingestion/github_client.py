import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class GithubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("GITHUB_API_TOKEN") or os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GitHub token not found. Set GITHUB_API_TOKEN or GITHUB_TOKEN.")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
        }

    def get(self, endpoint: str, params: dict | None = None) -> Any:
        url = f"{self.BASE_URL}{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)

        if response.status_code == 403 and "rate limit" in response.text.lower():
            self.handle_rate_limit(response)
            response = requests.get(url, headers=self.headers, params=params)

        response.raise_for_status()
        return response.json()

    def paginate(self, endpoint: str, params: dict | None = None, per_page: int = 100):
        page = 1
        params = params.copy() if params else {}

        while True:
            params.update({"per_page": per_page, "page": page})
            data = self.get(endpoint, params)

            if not data:
                break

            for item in data:
                yield item
            page += 1

    def handle_rate_limit(self, response: requests.Response):
        reset_time = response.headers.get("X-RateLimit-Reset")
        if not reset_time:
            time.sleep(5)
            return
        sleep_for = max(int(reset_time) - int(time.time()) + 1, 1)
        print(f"Rate limit hit. Sleeping {sleep_for}s")
        time.sleep(sleep_for)
