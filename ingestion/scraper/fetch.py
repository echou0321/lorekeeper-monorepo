import time
import random
import requests

SESSION = requests.Session()
SESSION.headers.update({
    'User-Agent': 'Lorekeeper/1.0 (lorekeeper.app; fan research tool)'
})


def fetch(url: str) -> str:
    time.sleep(random.uniform(1.0, 2.5))
    response = SESSION.get(url, timeout=10)
    response.raise_for_status()
    return response.text
