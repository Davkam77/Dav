import json
import logging
import os
import requests
from pathlib import Path

logger = logging.getLogger(__name__)

def load_cache():
    """Load search cache from file."""
    cache_path = Path('cache/search_cache.json')
    if cache_path.exists():
        with cache_path.open(encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    """Save search cache to file."""
    cache_path = Path('cache/search_cache.json')
    cache_path.parent.mkdir(exist_ok=True)
    with cache_path.open('w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def load_global_favorites():
    """Load global favorites from file."""
    path = Path('cache/favorites.json')
    if path.exists():
        with path.open(encoding='utf-8') as f:
            return json.load(f)
    return []

def save_global_favorites(data):
    """Save global favorites to file."""
    path = Path('cache/favorites.json')
    path.parent.mkdir(exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_telegram_to(chat_id: str, title: str, link: str):
    """Send a Telegram notification."""
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.warning('Telegram token not found')
        return

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': f'📢 New Task:\n{title}\n🔗 {link}',
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f'Telegram send error: {e}')