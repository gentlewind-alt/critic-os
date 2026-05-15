from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import os
import traceback

app = FastAPI(title="XLM Emotion API v6 - Robust Load")

MODEL_PATH = os.getenv("MODEL_PATH", ".") 
device = 0 if torch.cuda.is_available() else -1

model = None
tokenizer = None
load_error = None

def get_id2label():
    return {
        0: "admiration", 1: "amusement", 2: "anger", 3: "annoyance", 4: "approval", 5: "caring",
        6: "confusion", 7: "curiosity", 8: "desire", 9: "disappointment", 10: "disapproval", 11: "disgust",
        12: "embarrassment", 13: "excitement", 14: "fear", 15: "gratitude", 16: "grief", 17: "joy",
        18: "love", 19: "nervousness", 20: "optimism", 21: "pride", 22: "realization", 23: "relief",
        24: "remorse", 25: "sadness", 26: "surprise", 27: "neutral"
    }

id2label = get_id2label()

@app.on_event("startup")
def load_model():
    global model, tokenizer, load_error
    print(f"🚀 Loading model from: {MODEL_PATH}")
    try:
        # Check if sentencepiece is actually available
        import sentencepiece
        print("✅ sentencepiece is installed")
        
        # Try loading tokenizer. We don't specify use_fast, let AutoTokenizer decide
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)
        
        if device == 0:
            model = model.to("cuda")
        model.eval()
        print("✅ Model & Tokenizer loaded!")
    except ImportError:
        load_error = "ImportError: sentencepiece is not installed. Please add it to requirements.txt"
        print(f"❌ {load_error}")
    except Exception as e:
        load_error = f"Load Failure: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {load_error}")

class PredictionRequest(BaseModel):
    text: str
    threshold: float = 0.3

@app.get("/")
def home():
    return {
        "status": "online", 
        "model_ready": model is not None, 
        "error": load_error
    }

@app.post("/predict")
def predict(request: PredictionRequest):
    if model is None:
        raise HTTPException(status_code=500, detail=f"Model not loaded: {load_error}")
    
    try:
        inputs = tokenizer(
            request.text.strip(), 
            return_tensors="pt", 
            truncation=True, 
            max_length=512
        )
        
        if device == 0:
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.sigmoid(outputs.logits).squeeze().cpu().numpy()

        emotion_dict = {id2label[i]: float(probs[i]) for i in range(len(probs))}
        sorted_emotions = sorted(emotion_dict.items(), key=lambda x: x[1], reverse=True)
        neutral_score = emotion_dict.get("neutral", 0.0)
        
        filtered = sorted_emotions
        if neutral_score > 0.48 and len(sorted_emotions) > 1:
            filtered = [e for e in sorted_emotions if e[0] != "neutral"]

        if not filtered:
            filtered = [("neutral", neutral_score)]

        detected = {
            k: round(v, 4) for k, v in filtered 
            if v >= request.threshold or (k == filtered[0][0])
        }
        
        return {
            "emotions_detected": dict(sorted(detected.items(), key=lambda x: x[1], reverse=True)),
            "Emotion": list(detected.keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")
