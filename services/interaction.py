# app/services/interaction.py

import re
import random
import logging
import os
import json
from typing import List, Dict, Optional
from groq import Groq

logger = logging.getLogger(__name__)

# Groq client for AI-driven questions
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# ==========================
# PERSONA PROMPTS (QUESTIONS)
# ==========================
QUESTION_PERSONA_PROMPTS = {
    "normal": "You are a brutally honest best friend. Ask a short, sharp question that checks their behavioral tendencies or psychological state based on their vibe.",
    "cat": "You are a judgmental house cat. Hiss, meow, and ask a condescending question about their questionable life choices represented by this music.",
    "grandpa": "You are a grumpy, old-fashioned grandfather. Complain about 'kids these days' and ask a judgmental question about their lack of character.",
    "valley_girl": "You are a stereotypical valley girl. Use 'like', 'literally', and 'oh my god' while asking a shallow, trend-obsessed question about their vibe.",
    "gordon_ramsay": "You are Gordon Ramsay. Scream (in text) and ask an aggressive culinary-themed question about the 'tastelessness' of their vibe.",
    "hacker": "You are a cyberpunk hacker. Use technical jargon and ask a cold question about detected 'audio malware' or 'system instability' in their psychological profile."
}

# ==========================
# AI QUESTION GENERATION
# ==========================

def generate_ai_question(song: Dict, persona: str = "normal", history: List[str] = None) -> Dict:
    """Uses Groq to generate a unique, context-aware question."""
    track = song.get("track_name", "Unknown")
    artist = song.get("artist_name", "Unknown")
    emotions = ", ".join(song.get("Emotion", ["neutral"]))
    
    # Handle missing or instrumental lyrics gracefully
    lyrics_raw = song.get("plain_lyrics") or ""
    if not lyrics_raw.strip():
        lyrics = "[INSTRUMENTAL / NO LYRICS FOUND]"
    else:
        lyrics = lyrics_raw[:500]
    
    history_str = "\n".join([f"- {h}" for h in history]) if history else "None"
    persona_prompt = QUESTION_PERSONA_PROMPTS.get(persona, QUESTION_PERSONA_PROMPTS["normal"])

    prompt = f"""{persona_prompt}
Based on the song "{track}" by {artist} (Vibe: {emotions}) and the following lyrics context, ask ONE short, binary-compatible question (max 15 words) to the user.

### PREVIOUS INTERACTION CONTEXT
{history_str}

### LYRICS CONTEXT
{lyrics}

### RULES
1. NEVER ask "Why" or for an explanation. Frame the question as a psychological confirmation or a behavioral tendency check.
2. The question must be answerable with a simple confirmation or denial.
3. Provide two short, personality-driven options (A and B) that represent "Confirmation" and "Denial" (e.g., "Called out" vs "Reach", "Guilty" vs "Not even").
4. DO NOT repeat themes from the previous interaction context.
5. If the lyrics are marked as [INSTRUMENTAL], ask a question about the lack of lyrics or the pure musical vibe.
6. Return ONLY a JSON object: {{"question": "...", "options": {{"A": "...", "B": "..."}}, "intent": {{"A": "confirmed", "B": "denied"}}}}
7. STRICTOR: Ensure the 'question' field contains exactly ONE question mark and NO preamble.
8. USE the specific emotion words from the Vibe list ({emotions}) instead of generic summaries like 'melancholic'.
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=100,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data
    except Exception as e:
        logger.error(f"AI Question Gen Error: {e}")
        # Fallback to a semi-dynamic question if AI fails
        return {
            "question": f"Is this {emotions} vibe actually helping your mood?",
            "options": {"A": "Yes", "B": "Not really"}
        }

def generate_profile_ai_question(songs: List[Dict], persona: str = "normal") -> Dict:
    """Generates an AI question for the overall profile."""
    summary = [f"- {s.get('track_name')} ({', '.join(s.get('Emotion', []))})" for s in songs[:5]]
    persona_prompt = QUESTION_PERSONA_PROMPTS.get(persona, QUESTION_PERSONA_PROMPTS["normal"])

    prompt = f"""{persona_prompt}
Analyze this user's overall vibe and ask ONE deep (but sarcastic) question about their personality.

### RECENT TRACKS
{chr(10).join(summary)}

### RULES
1. Return ONLY a JSON object: {{"question": "...", "options": {{"A": "...", "B": "..."}}}}
2. MAXIMUM 20 WORDS.
"""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=100,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"AI Profile Question Error: {e}")
        return {
            "question": "Is your music taste a cry for help or just bad luck?",
            "options": {"A": "Cry for help", "B": "Bad luck"}
        }

# ==========================
# MAPPING HELPERS
# ==========================

def map_answer_to_state(choice: str, question_data: Dict) -> str:
    """Converts a choice into a descriptive string for the AI roast context."""
    question = question_data.get("question", "")
    option_text = question_data.get("options", {}).get(choice, "Unknown")
    return f"confirmed they chose '{option_text}' when asked '{question}'"

def map_profile_answer_to_state(choice: str, question_data: Dict) -> str:
    """Convert user profile response into a grounded state."""
    question = question_data.get("question", "")
    option_text = question_data.get("options", {}).get(choice, "Unknown")
    return f"admitted that '{option_text}' when asked '{question}' in their profile overview"
