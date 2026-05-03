# app/services/emotion.py

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from typing import Dict, List
import os
import logging

logger = logging.getLogger(__name__)

# ==========================
# CONFIG
# ==========================
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MODEL_PATH = os.getenv("EMOTION_MODEL_PATH", "./emotion_model")

EMOTION_LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude",
    "grief", "joy", "love", "nervousness", "optimism", "pride",
    "realization", "relief", "remorse", "sadness", "surprise", "neutral"
]

_model = None
_tokenizer = None
_num_labels = None


# ==========================
# MODEL LOADER (SINGLETON)
# ==========================
def load_emotion_model():
    global _model, _tokenizer, _num_labels

    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"Emotion model not found: {MODEL_PATH}")

        logger.info(f"Loading emotion model from: {MODEL_PATH}")

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

        _model.to(DEVICE)
        _model.eval()

        _num_labels = len(EMOTION_LABELS)

        logger.info(f"Emotion model loaded | labels: {_num_labels}")

    return _model, _tokenizer, _num_labels


# ==========================
# CORE PREDICTION
# ==========================
def predict_emotion(lyrics: str, threshold: float = 0.05) -> Dict:

    model, tokenizer, num_labels = load_emotion_model()

    if not lyrics or len(lyrics.strip()) < 15:
        return {
            "emotions_detected": {},
            "Emotion": ["neutral"]
        }

    inputs = tokenizer(
        lyrics,
        padding="max_length",
        truncation=True,
        max_length=256,
        return_tensors="pt"
    )

    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits

    probs = torch.sigmoid(logits).squeeze().cpu().numpy()

    emotion_dict = {
        label: float(prob)
        for label, prob in zip(EMOTION_LABELS[:num_labels], probs)
    }

    detected = {
        k: round(v, 4)
        for k, v in emotion_dict.items()
        if v >= threshold
    }

    detected = dict(sorted(detected.items(), key=lambda x: x[1], reverse=True))

    emotion_list = list(detected.keys()) if detected else ["neutral"]

    return {
        "emotions_detected": detected,
        "Emotion": emotion_list
    }


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


# ==========================
# STREAMING PIPELINE
# ==========================
def process_emotions(songs: List[Dict]):
    """
    Generator for pipeline streaming
    """

    yield {
        "type": "log",
        "content": "analyzing emotional patterns..."
    }

    for i, song in enumerate(songs):

        yield {
            "type": "log",
            "content": f"processing emotion for {song.get('track_name')}..."
        }

        enriched = process_song_emotion(song)

        yield {
            "type": "emotion",
            "data": enriched,
            "index": i
        }

    yield {
        "type": "log",
        "content": "emotion analysis complete"
    }


# ==========================
# NON-STREAM MODE (OPTIONAL)
# ==========================
def process_emotions_batch(songs: List[Dict]) -> List[Dict]:

    results = []

    for song in songs:
        results.append(process_song_emotion(song))

    return results