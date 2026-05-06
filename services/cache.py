import os
import redis
import json
import logging

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
