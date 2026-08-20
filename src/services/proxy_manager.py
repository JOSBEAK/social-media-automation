# src/services/proxy_manager.py
import threading
import json
from typing import List, Optional

class ProxyManager:
    def __init__(self, proxy_file: str = "proxies.json"):
        self.proxies: List[str] = []
        self._index = 0
        self._lock = threading.Lock()
        self._load_proxies(proxy_file)

    def _load_proxies(self, file_path: str):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                proxies = json.load(f)
            if not isinstance(proxies, list) or not all(isinstance(item, str) for item in proxies):
                raise ValueError("proxies.json must contain a JSON array of proxy URLs")
            self.proxies = proxies
            print(f"[ProxyManager] Loaded {len(self.proxies)} proxies.")
        except FileNotFoundError:
            print("[ProxyManager] No proxies.json found. Running without proxies.")
            self.proxies = []
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"Invalid proxy configuration in {file_path}: {exc}") from exc

    def get_next(self) -> Optional[str]:
        if not self.proxies:
            return None
        with self._lock:
            proxy = self.proxies[self._index % len(self.proxies)]
            self._index += 1
            return proxy
