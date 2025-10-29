import json
import secrets
from pathlib import Path
from typing import Dict, List

from mesh.utils.logging import get_logger

logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
KEYS_FILE = "bootnode_utils/bootnode_rest_keys.json"

# Load keys at startup
def load_api_keys() -> List[Dict]:
    try:
        with open(KEYS_FILE, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        logger.error(f"Error loading API keys: {e}")
        return []

def get_active_keys(keys: List[Dict]) -> set[str]:
    return {entry["key"] for entry in keys if entry.get("active", True)}

def save_api_keys(keys):
    try:
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=4)
            logger.info(f"Saved keys to {KEYS_FILE}")
    except Exception as e:
        logger.error(f"Error saving API keys {e}", exc_info=True)

def add_api_key(owner: str, key: str = None, active: bool = True):
    keys = load_api_keys()
    if key is None:
        key = f"key-{owner}-{secrets.token_hex(6)}"  # noqa: F821
    # Check for duplicates
    if any(k["key"] == key for k in keys):
        logger.info(f"Key {key} already exists!")
        return
    # Look for existing entry for this owner
    for entry in keys:
        if entry["owner"] == owner:
            entry["key"] = key
            entry["active"] = active
            save_api_keys(keys)
            logger.info(f"Updated API key for {owner}: {key}")
            return

    keys.append({"owner": owner, "key": key, "active": active})
    save_api_keys(keys)
    logger.info(f"Added API key for {owner}: {key}")
