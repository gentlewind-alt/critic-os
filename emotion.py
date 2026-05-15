# app/services/emotion.py

import hashlib
from services.cache import cache_get, cache_set
import os
import logging
import requests
from typing import Dict, List

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger(__name__)

# ==========================
# CONFIG
# ==========================
# Local model path: ../emotion_model (Relative to workspace root)
MODEL_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "emotion_model"))
API_URL = os.getenv("HF_INFERENCE_URL", "https://router.huggingface.co/hf-inference/models/samarthruckstar/emotion_label_model")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")

_emotion_pipeline = None

def get_emotion_pipeline():
    global _emotion_pipeline
    if _emotion_pipeline is None:
        if pipeline is None:
            logger.error("Transformers library not installed. Local model unavailable.")
            return None
        try:
            if not os.path.exists(MODEL_PATH):
                logger.error(f"Local model path not found: {MODEL_PATH}")
                return None
            logger.info(f"Loading local emotion model from {MODEL_PATH}...")
            _emotion_pipeline = pipeline("text-classification", model=MODEL_PATH, top_k=None)
            logger.info("Local emotion model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load local emotion model: {e}")
            return None
    return _emotion_pipeline

EMOTION_LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude",
    "grief", "joy", "love", "nervousness", "optimism", "pride",
    "realization", "relief", "remorse", "sadness", "surprise", "neutral"
]


# ==========================
# CORE PREDICTION
# ==========================
def predict_emotion(lyrics: str, threshold: float = 0.05) -> Dict:
    """
    Attempts to get emotion predictions using a local model,
    falling back to HF Inference API if necessary.
    """
    default_result = {
        "emotions_detected": {},
        "Emotion": ["neutral"]
    }

    if not lyrics or len(lyrics.strip()) < 15:
        return default_result

    # Use SHA256 of lyrics as cache key
    lyrics_hash = hashlib.sha256(lyrics.encode('utf-8')).hexdigest()
    cache_key = f"emotion:{lyrics_hash}"
    
    cached = cache_get(cache_key)
    if cached:
        logger.info(f"     ✅ Found emotion analysis in Redis cache")
        return cached

    # 1. TRY LOCAL MODEL FIRST
    pipe = get_emotion_pipeline()
    if pipe:
        try:
            logger.info("     🧠 Using LOCAL model for emotion analysis...")
            # Pipeline returns a list of results
            raw_scores = pipe(lyrics)
            if isinstance(raw_scores, list) and len(raw_scores) > 0:
                scores = raw_scores[0] if isinstance(raw_scores[0], list) else raw_scores
                
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
                cache_set(cache_key, result, ex=2592000)
                return result
        except Exception as e:
            logger.error(f"Local Model Inference Error: {e}")

    # 2. FALLBACK TO HF API
    logger.info("     🌐 Falling back to HF Inference API...")
    if not HF_TOKEN:
        logger.warning("HUGGINGFACE_TOKEN not found. Emotion analysis defaulting to 'neutral'.")
        return default_result

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": lyrics, "parameters": {"return_all_scores": True}}

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 503:
            logger.info("HF Model is loading, retrying in 5s...")
            import time
            time.sleep(5)
            response = requests.post(API_URL, headers=headers, json=payload, timeout=15)

        response.raise_for_status()
        predictions = response.json()
        
        if isinstance(predictions, list) and len(predictions) > 0:
            scores = predictions[0] if isinstance(predictions[0], list) else predictions
            
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
            cache_set(cache_key, result, ex=2592000)
            return result
            
    except Exception as e:
        logger.error(f"HF Inference API Error: {e}")
    
    return default_result

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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_lyrics = "I am so happy and excited about this!"
    print(f"Testing with: {test_lyrics}")
    result = predict_emotion(test_lyrics)
    print(f"Result: {result}")