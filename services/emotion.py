# app/services/emotion.py

import hashlib
from services.cache import cache_get, cache_set
import os
import logging
import time
import requests
from typing import Dict, List, Optional

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger(__name__)
    
# ==========================
# CONFIG
# ==========================
MODEL_ID = os.getenv("EMOTION_MODEL_ID", "samarthruckstar/emotion_label_model")
API_URL = os.getenv("HF_INFERENCE_URL", ".")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
THRESHOLD = 0.1

# ==========================
# MODEL INITIALIZATION
# ==========================
_emotion_pipeline = None

def get_emotion_pipeline():
    """
    Lazy-load the emotion classification pipeline.
    Loads the model weights directly from Hugging Face.
    """
    global _emotion_pipeline
    if _emotion_pipeline is None:
        try:
            logger.info(f"     📥 Loading model '{MODEL_ID}' from Hugging Face...")
            _emotion_pipeline = pipeline(
                "text-classification",
                model=MODEL_ID,
                use_auth_token=HF_TOKEN,
                device=0 if os.getenv("DEVICE") == "cuda" else -1  # -1 for CPU, 0 for GPU
            )
            logger.info(f"     ✅ Model loaded successfully")
        except Exception as e:
            logger.error(f"❌ Failed to load model: {e}")
            raise
    return _emotion_pipeline

# ==========================
# LABEL MAP
# ==========================
id2label = {
    0: "admiration", 1: "amusement", 2: "anger", 3: "annoyance", 4: "approval", 5: "caring",
    6: "confusion", 7: "curiosity", 8: "desire", 9: "disappointment", 10: "disapproval", 11: "disgust",
    12: "embarrassment", 13: "excitement", 14: "fear", 15: "gratitude", 16: "grief", 17: "joy",
    18: "love", 19: "nervousness", 20: "optimism", 21: "pride", 22: "realization", 23: "relief",
    24: "remorse", 25: "sadness", 26: "surprise", 27: "neutral"
}

# ==========================
# CORE PREDICTION
# ==========================
def predict_emotion(lyrics: str, threshold: float = THRESHOLD) -> Dict:
    """
    Attempts to get emotion predictions using the HF Inference API,
    falling back to the local model if necessary.
    """
    default_result = {
        "emotions_detected": {},
        "Emotion": ["neutral"]
    }

    if not lyrics or len(lyrics.strip()) < 15:
        return default_result

    # Use SHA256 of lyrics as cache key to minimize inference calls
    lyrics_hash = hashlib.sha256(lyrics.encode('utf-8')).hexdigest()
    cache_key = f"emotion:{lyrics_hash}"
    
    cached = cache_get(cache_key)
    if cached:
        logger.info(f"     ✅ Found emotion analysis in cache")
        return cached

    if not HF_TOKEN:
        logger.warning("HUGGINGFACE_TOKEN not found. Emotion detection defaulted to 'neutral'.")
        return default_result

    emotion_dict = None

    # 1. TRY HF INFERENCE API FIRST
    logger.info(f"     🌐 Calling HF Inference API for model '{MODEL_ID}'...")
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    
    # Check if we are calling a custom FastAPI Space or the standard HF API
    is_custom_space = "hf.space" in API_URL
    if is_custom_space:
        payload = {"text": lyrics, "threshold": threshold}
    else:
        payload = {"inputs": lyrics, "parameters": {"return_all_scores": True}}

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)
        
        # Handle model loading (503 Service Unavailable)
        if response.status_code == 503:
            logger.info("     ⏳ HF Model is loading, retrying in 5s...")
            time.sleep(5)
            response = requests.post(API_URL, headers=headers, json=payload, timeout=15)

        response.raise_for_status()
        predictions = response.json()
        
        # Extract emotion_dict based on response format
        if isinstance(predictions, dict) and "emotions_detected" in predictions:
            # Format from custom FastAPI Space
            emotion_dict = {k: float(v) for k, v in predictions["emotions_detected"].items()}
            logger.info("     ✅ Received predictions from Custom Space API")
        elif isinstance(predictions, list) and len(predictions) > 0:
            # Format from standard Hugging Face Inference API
            scores = predictions[0] if isinstance(predictions[0], list) else predictions
            emotion_dict = {
                item['label']: float(item['score'])
                for item in scores
            }
            logger.info("     ✅ Received predictions from HF Inference API")
    except Exception as e:
        logger.error(f"     ❌ HF Inference API Error: {e}")

    # 2. FALLBACK TO LOCAL MODEL IF API FAILED
    if not emotion_dict and pipeline:
        try:
            logger.info(f"     🤖 Falling back to local model inference...")
            pipe = get_emotion_pipeline()
            if pipe:
                predictions = pipe(lyrics, top_k=None)
                if predictions:
                    scores = predictions[0] if isinstance(predictions[0], list) else predictions
                    emotion_dict = {}
                    for item in scores:
                        label = item['label']
                        score = float(item['score'])
                        # Normalize label (remove LABEL_ prefix if present)
                        if label.startswith("LABEL_"):
                            try:
                                idx = int(label.split("_")[1])
                                label = id2label.get(idx, label)
                            except:
                                pass
                        emotion_dict[label] = score
                    logger.info("     ✅ Local model inference successful")
        except Exception as e:
            logger.error(f"     ❌ Local Model Inference Error: {e}")

    # PROCESS RESULTS
    if emotion_dict:
        try:
            # Sort all emotions by score descending
            sorted_emotions = sorted(emotion_dict.items(), key=lambda x: x[1], reverse=True)
            
            # CUSTOM LOGIC: If neutral > 0.48, drop it and take the next top emotion
            neutral_score = emotion_dict.get("neutral", 0.0)
            if neutral_score > 0.48:
                logger.info(f"     ⚖️ Neutral score {neutral_score:.4f} > 0.48. Dropping neutral.")
                filtered_emotions = [e for e in sorted_emotions if e[0] != "neutral"]
            else:
                filtered_emotions = sorted_emotions

            # Ensure we have at least one emotion after filtering
            if not filtered_emotions:
                filtered_emotions = [("neutral", neutral_score)]

            detected = {
                k: round(v, 4)
                for k, v in filtered_emotions
                if v >= threshold or (k == filtered_emotions[0][0])
            }
            
            detected = dict(sorted(detected.items(), key=lambda x: x[1], reverse=True))
            emotion_list = list(detected.keys())
            
            result = {
                "emotions_detected": detected,
                "Emotion": emotion_list
            }
            cache_set(cache_key, result, ex=2592000)
            return result
        except Exception as e:
            logger.error(f"     ❌ Error processing emotion results: {e}")

    return default_result


# ==========================
# BATCH PROCESSING
# ==========================
import concurrent.futures

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

def refresh_hf_token():
    """Utility to refresh token from env and reload model (called by pipeline)"""
    global HF_TOKEN, _emotion_pipeline
    from dotenv import load_dotenv
    load_dotenv(override=True)
    HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
    _emotion_pipeline = None  # Reset pipeline so it reloads with new token
    logger.info("     ♻️ Hugging Face token refreshed. Pipeline will reload on next inference.")
