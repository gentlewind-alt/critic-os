import os
import redis
import json
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Load Redis URL from environment
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.from_url(redis_url, decode_responses=True)

# For Spotify tokens, we might need a non-decoded client if spotipy expects bytes
# but spotipy's RedisCacheHandler usually handles it. 
# Actually, spotipy's RedisCacheHandler uses json.dumps/loads internally, 
# so decode_responses=True should be fine if it handles strings, 
# but often it's safer to have a raw client for spotipy.
redis_client_raw = redis.from_url(redis_url, decode_responses=False)

def get_redis_client():
    return redis_client

def get_redis_client_raw():
    return redis_client_raw

def cache_get(key):
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Redis get error for {key}: {e}")
    return None

def cache_set(key, value, ex=3600):
    try:
        redis_client.set(key, json.dumps(value), ex=ex)
    except Exception as e:
        logger.error(f"Redis set error for {key}: {e}")

# ==========================
# USER LIMIT HELPERS
# ==========================

def has_reached_limit(user_id: str) -> bool:
    """Checks if the user has already performed their one-time analysis."""
    if not user_id:
        return False
    
    # DEVELOPMENT GAP: Allow bypass for specific users
    bypass_raw = os.getenv("BYPASS_LIMIT_USERS", "")
    bypass_users = [u.strip() for u in bypass_raw.split(",") if u.strip()]
    
    if user_id in bypass_users:
        logger.info(f"[DIAGNOSTIC] Bypass check: SUCCESS for {user_id}")
        return False
    
    logger.info(f"[DIAGNOSTIC] Bypass check: FAILED for {user_id}. Whitelist: {bypass_users}")

    try:
        return redis_client.get(f"user_limit:{user_id}") == "spent"
    except Exception as e:
        logger.error(f"Redis limit check error for {user_id}: {e}")
        return False

def set_user_limit_spent(user_id: str):
    """Marks the user's one-time analysis as spent."""
    if not user_id:
        return

    # DEVELOPMENT GAP: Don't mark as spent for bypass users
    bypass_users = os.getenv("BYPASS_LIMIT_USERS", "").split(",")
    if user_id in bypass_users:
        return

    try:
        # Set with no expiration (or very long one, e.g., 1 year)
        redis_client.set(f"user_limit:{user_id}", "spent", ex=31536000) 
        logger.info(f"Analysis limit set for user: {user_id}")
    except Exception as e:
        logger.error(f"Redis limit set error for {user_id}: {e}")

# ==========================
# REPORT STORAGE
# ==========================

def save_user_report(user_id: str, report_data: Dict):
    """Saves the final analysis report for the dossier page."""
    if not user_id:
        return
    try:
        key = f"user_report:{user_id}"
        redis_client.set(key, json.dumps(report_data), ex=31536000) # Save for 1 year
        logger.info(f"Report saved for user: {user_id}")
    except Exception as e:
        logger.error(f"Redis report save error for {user_id}: {e}")

def get_user_report(user_id: str) -> Optional[Dict]:
    """Retrieves the analysis report for the dossier page."""
    if not user_id:
        return None
    try:
        key = f"user_report:{user_id}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Redis report get error for {user_id}: {e}")
    return None
