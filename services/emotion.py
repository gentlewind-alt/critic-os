# app/services/emotion.py

import hashlib
from services.cache import cache_get, cache_set
import os
import logging
import requests
from typing import Dict, List

logger = logging.getLogger(__name__)

# ==========================
# CONFIG
# ==========================
API_URL = os.getenv("HF_INFERENCE_URL", "https://api-inference.huggingface.co/models/samarthruckstar/emotion_label_model")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

EMOTION_LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude",
    "grief", "joy", "love", "nervousness", "optimism", "pride",
    "realization", "relief", "remorse", "sadness", "surprise", "neutral"
]


# ==========================
# CORE PREDICTION (API)
# ==========================
def predict_emotion(lyrics: str, threshold: float = 0.05) -> Dict:
    """
    Calls the Hugging Face Inference API to get emotion predictions.
    """
    if not lyrics or len(lyrics.strip()) < 15:
        return {
            "emotions_detected": {},
            "Emotion": ["neutral"]
        }

    # Use SHA256 of lyrics as cache key
    lyrics_hash = hashlib.sha256(lyrics.encode('utf-8')).hexdigest()
    cache_key = f"emotion:{lyrics_hash}"
    
    cached = cache_get(cache_key)
    if cached:
        logger.info(f"     ✅ Found emotion analysis in Redis cache")
        return cached

    if not HF_TOKEN:
        logger.warning("HUGGINGFACE_TOKEN not found in environment variables. Emotion analysis will default to 'neutral'.")
        return {"emotions_detected": {}, "Emotion": ["neutral"]}

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": lyrics, "parameters": {"return_all_scores": True}}

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
        
        # Handle model loading state (HF returns 503 while loading)
        if response.status_code == 503:
            logger.info("HF Model is loading, retrying in 5s...")
            import time
            time.sleep(5)
            response = requests.post(API_URL, headers=headers, json=payload, timeout=15)

        response.raise_for_status()
        predictions = response.json()
        
        # HF Inference API for classification typically returns [[{"label": "...", "score": ...}, ...]]
        if isinstance(predictions, list) and len(predictions) > 0:
            if isinstance(predictions[0], list):
                scores = predictions[0]
            else:
                scores = predictions # Some tasks return direct list
            
            emotion_dict = {
                item['label']: float(item['score'])
                for item in scores
            }
            
            detected = {
                k: round(v, 4)
                for k, v in emotion_dict.items()
                if v >= threshold
            }
            
            detected = dict(sorted(detected.items(), key=lambda x: x[1], reverse=True))
            emotion_list = list(detected.keys()) if detected else ["neutral"]
            
            result = {
                "emotions_detected": detected,
                "Emotion": emotion_list
            }
            
            # Cache for 30 days
            cache_set(cache_key, result, ex=2592000)
            return result
            
    except Exception as e:
        logger.error(f"HF Inference API Error: {e}")
        
import concurrent.futures

# ==========================
# BATCH PROCESSING
# ==========================
def process_emotions_batch(songs: List[Dict]) -> List[Dict]:
    """
    Parallelized emotion detection for a batch of songs.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(process_song_emotion, songs))
    return results


# ==========================
# SINGLE SONG
# ==========================
def process_song_emotion(song: Dict) -> Dict:
    """
    Enrich one song with emotion data
    """

    lyrics = song.get("plain_lyrics", "")
    lyrics_found = song.get("lyrics_found", False)

    if lyrics_found and lyrics:
        result = predict_emotion(lyrics)
        return {
            **song,
            "emotion_analysis": {
                "emotions_detected": result["emotions_detected"]
            },
            "Emotion": result["Emotion"]
        }

    return {
        **song,
        "emotion_analysis": {"emotions_detected": {}},
        "Emotion": ["neutral"]
    }