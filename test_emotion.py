from transformers import pipeline
import os

# The model ID used in your project
MODEL_ID = "samarthruckstar/emotion_label_model"

# Mapping from services/emotion.py
EMOTION_LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude",
    "grief", "joy", "love", "nervousness", "optimism", "pride",
    "realization", "relief", "remorse", "sadness", "surprise", "neutral"
]

print(f"--- Loading model: {MODEL_ID} ---")
pipe = pipeline("text-classification", model=MODEL_ID, top_k=None)

# Sample test cases
test_lines = [
    "I finally got the job! I can't believe it, this is amazing!",
    "I am so tired of this constant rain and gray sky, it makes me so miserable.",
    "Get out of my room! You have no right to touch my things!",
    "I wonder how birds manage to migrate such long distances without getting lost?"
]

def get_label_name(label_str):
    # If it's already a word, return it
    if not label_str.startswith("LABEL_"):
        return label_str
    try:
        idx = int(label_str.split("_")[1])
        return EMOTION_LABELS[idx]
    except (IndexError, ValueError):
        return label_str

print("\n--- Inference Results ---")
for line in test_lines:
    results = pipe(line)[0]
    top_result = max(results, key=lambda x: x['score'])
    
    raw_label = top_result['label']
    emotion = get_label_name(raw_label)
    confidence = top_result['score'] * 100
    
    print(f"a {{{emotion}}} statement - {confidence:.1f}% confidence. Emotion detected: {emotion}")
