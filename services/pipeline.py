# app/services/pipeline.py

import time
from typing import List, Dict

from services.processing import process_songs_batch
from services.emotion import process_song_emotion
from services.roast import generate_roast_stream, generate_profile_roast_stream
from services.interaction import build_question_data


# ==========================
# STATE ENUM
# ==========================
class PipelineState:
    INIT = "INIT"
    LOADING = "LOADING"
    LYRICS = "LYRICS"
    EMOTION = "EMOTION"
    INSIGHT = "INSIGHT"
    ROAST = "ROAST"
    FINAL = "FINAL"


# ==========================
# HELPERS
# ==========================

def _event(event_type, value):
    return {
        "type": event_type,
        "value": value
    }


def _log(text):
    return {
        "type": "log",
        "content": f"> {text}"
    }


# ==========================
# PROFILE BUILDER
# ==========================
def _build_profile(songs: List[Dict]) -> Dict:

    emotions = []

    for s in songs:
        emotions.extend(s.get("Emotion", []))

    if not emotions:
        return {
            "dominant_emotion": "neutral",
            "confidence": 0.0,
            "pattern": "undefined"
        }

    dominant = max(set(emotions), key=emotions.count)

    confidence = round(emotions.count(dominant) / len(emotions), 2)
    spectrum = sorted(list(set(emotions)))

    return {
        "dominant_emotion": dominant,
        "confidence": confidence,
        "pattern": f"{dominant}-driven listening loop",
        "spectrum": spectrum
    }


# ==========================
# OPTIMIZED PIPELINE
# ==========================
def run_pipeline_optimized(enriched_songs: List[Dict], persona: str = "normal", custom_prompt: str = None, profile_custom_prompt: str = None, collection_name: str = "your collection"):
    """
    Optimized pipeline that processes each song (emotion + roast) sequentially.
    Now includes AI-driven questions and session history.
    """
    session_history = [] # Track interactions for context

    # ==========================
    # INIT
    # ==========================
    yield _event("state", PipelineState.INIT)
    yield _log(f"Initializing analysis for collection: {collection_name}...")
    time.sleep(0.5)

    # ==========================
    # INSIGHT STAGE (PROFILE)
    # ==========================
    yield _event("state", PipelineState.INSIGHT)
    yield _log("Generating overall behavioral profile...")
    yield _log("Connecting to GROQ AI Core...")

    from services.interaction import generate_profile_ai_question, map_profile_answer_to_state
    profile_q_module = generate_profile_ai_question(enriched_songs, persona)

    yield {
        "type": "profile_start",
        "question_module": profile_q_module
    }

    # In this streaming mode, we can't 'wait' for the answer in the same loop
    # unless we use a request/response pattern. For now, we simulate the state
    # if the UI provides it, or generate the roast based on the question asked.
    
    interaction_state = f"Persona asked: '{profile_q_module.get('question')}'"

    try:
        from services.roast import generate_profile_roast_stream
        for token in generate_profile_roast_stream(enriched_songs, persona, profile_custom_prompt, interaction_state):
            yield {
                "type": "profile_token",
                "text": token
            }
    except Exception as e:
        yield _log(f"AI Error: {str(e)}")
        yield { "type": "profile_token", "text": "[SYSTEM ERROR: AI CORE FAILED TO RESPOND]" }

    yield {
        "type": "profile_end"
    }

    session_history.append(interaction_state)
    time.sleep(1)

    # ==========================
    # SEQUENTIAL SONG PROCESSING
    # ==========================
    yield _event("state", PipelineState.ROAST)
    yield _log("Executing behavioral critique song-by-song...")

    from services.interaction import generate_ai_question, map_answer_to_state
    from services.roast import generate_roast_stream, generate_short_impression_stream

    for i, song in enumerate(enriched_songs):
        # 1. Update Display (Cover + Emotions)
        yield {
            "type": "coverflow",
            "song": {
                "track": song.get("track_name"),
                "artist": song.get("artist_name"),
                "image": song.get("album_image", "")
            },
            "index": i
        }
        
        # Get max confidence for this song
        probs = song.get("emotion_analysis", {}).get("emotions_detected", {}).values()
        max_prob = max(probs) if probs else 0

        yield {
            "type": "emotion",
            "data": song.get("Emotion", ["neutral"]),
            "confidence": max_prob
        }
        
        yield _log(f"Analyzing {song.get('track_name')}...")

        # 2. Roast this song (TIERED + INTERACTIVE)
        if i < 5:
            # FULL ROAST WITH AI QUESTION
            q_data = generate_ai_question(song, persona, session_history)
            
            yield {
                "type": "roast_start",
                "index": i,
                "track": song.get("track_name"),
                "artist": song.get("artist_name"),
                "question_module": q_data
            }
            
            # Weave previous interactions into the current roast
            current_context = " | ".join(session_history[-2:]) if session_history else None
            generator = generate_roast_stream(song, persona, custom_prompt, current_context)
            
            session_history.append(f"Discussed {song.get('track_name')}: asked '{q_data.get('question')}'")
        else:
            # SHORT IMPRESSION
            yield {
                "type": "roast_start",
                "index": i,
                "track": song.get("track_name"),
                "artist": song.get("artist_name")
            }
            generator = generate_short_impression_stream(song, persona)

        song_roast_chunks = []
        try:
            for token in generator:
                song_roast_chunks.append(token)
                yield {
                    "type": "roast_token",
                    "text": token,
                    "index": i
                }
        except Exception as e:
            yield { "type": "roast_token", "text": f"[AI Error: {str(e)}]", "index": i }

        song["roast"] = "".join(song_roast_chunks)

        yield {
            "type": "roast_end",
            "index": i
        }
        
        if i < len(enriched_songs) - 1:
            time.sleep(3 if i >= 5 else 5)

    # ==========================
    # FINAL STAGE
    # ==========================
    from services.roast import generate_final_verdict_stream
    yield _event("state", PipelineState.FINAL)
    profile = _build_profile(enriched_songs)

    yield {
        "type": "final_start",
        "profile": profile
    }

    verdict_chunks = []
    try:
        for token in generate_final_verdict_stream(enriched_songs, persona, collection_name):
            verdict_chunks.append(token)
            yield {
                "type": "final_token",
                "text": token
            }
    except Exception as e:
        yield { "type": "final_token", "text": "[FINAL VERDICT ERROR]" }

    yield {
        "type": "final_end",
        "verdict": "".join(verdict_chunks)
    }

    yield _log("Session complete")
