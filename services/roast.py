# app/services/roast.py

import os
import logging
import csv
import random
import json
from typing import Dict, List, Generator
from groq import Groq

logger = logging.getLogger(__name__)

# ==========================
# GROQ SETUP
# ==========================
groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)
GROQ_MODEL = "llama-3.3-70b-versatile"#"meta-llama/llama-4-scout-17b-16e-instruct"

# ==========================
# JOKES DATASET LOADING
# ==========================
JOKES_BY_EMOTION = {}

load_jokes_called = False

def load_jokes():
    global JOKES_BY_EMOTION, load_jokes_called
    if load_jokes_called:
        return
    load_jokes_called = True
    
    file_path = "jokes_subset.csv"
    if not os.path.exists(file_path):
        # Fallback to full file if subset is missing
        file_path = "jokes_with_emotions.csv"
    
    if not os.path.exists(file_path):
        logger.warning(f"Jokes dataset not found. Humor injection disabled.")
        return

    try:
        with open(file_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                emotion = row.get('dominant_emotion', 'neutral')
                if emotion not in JOKES_BY_EMOTION:
                    JOKES_BY_EMOTION[emotion] = []
                JOKES_BY_EMOTION[emotion].append({
                    "setup": row.get('title', ''),
                    "punchline": row.get('selftext', '')
                })
        logger.info(f"Successfully loaded jokes for {len(JOKES_BY_EMOTION)} emotions.")
    except Exception as e:
        logger.error(f"Error loading jokes dataset: {e}")

# load_jokes() # REMOVED: Load lazily in get_random_joke

def get_random_joke(emotion: str) -> str:
    load_jokes() # Lazy load
    jokes = JOKES_BY_EMOTION.get(emotion, JOKES_BY_EMOTION.get('neutral', []))
    if not jokes:
        return ""
    joke = random.choice(jokes)
    return f"Setup: {joke['setup']}\nPunchline: {joke['punchline']}"

# ==========================
# PERSONA DEFINITIONS
# ==========================
PERSONAS = {
    "normal": {
        "desc": "a regular, brutally honest best friend",
        "style": "Direct, casual, and sharp. No heavy metaphors."
    },
    "cat": {
        "desc": "a judgmental yet strangely caring house cat",
        "style": "Condescending, fickle, but occasionally purring. You are easily unimpressed. You MUST frequently use 'meow', 'purr', 'hiss', or 'nyan' in your sentences. You care about the user's well-being but hate their music."
    },
    "grandpa": {
        "desc": "a grumpy, old-fashioned grandfather who hates modern technology",
        "style": "Complaining, nostalgic for 'real' music, and easily confused by gadgets. You MUST use phrases like 'back in my day', 'kids these days', 'turn that racket down', or 'it all sounds like static to me'. You think anything made after 1975 isn't music."
    }
}
# ==========================
# PROMPT BUILDER
# ==========================

def build_prompt(song: Dict, persona: str = "normal", custom_prompt: str = None, interaction_state: str = None) -> str:
    track = song.get("track_name", "Unknown Track")
    artist = song.get("artist_name", "Unknown Artist")
    
    # Handle missing or instrumental lyrics gracefully
    lyrics_raw = song.get("plain_lyrics") or ""
    lyrics = lyrics_raw[:1000]
    lyrics_found = song.get("lyrics_found", bool(lyrics))

    # Metadata for better context
    song_emotions = song.get("Emotion", ["neutral"])
    primary_emotion = song_emotions[0] if song_emotions else "neutral"
    emotions_str = ", ".join(song_emotions)

    # Humor Injection
    reference_joke = get_random_joke(primary_emotion)
    joke_instruction = ""
    if reference_joke:
        joke_instruction = f"""
### HUMOR REFERENCE (STYLE ONLY)
Reference this Reddit joke ONLY for its comedic timing and punchline structure. 
DO NOT mention its specific topics (e.g., specific objects, people, or scenarios in the joke).
{reference_joke}
"""

    persona_info = PERSONAS.get(persona, PERSONAS["normal"])
    persona_desc = persona_info["desc"]
    persona_style = persona_info["style"]

    if custom_prompt:
        base_instructions = custom_prompt
    elif not lyrics_found:
        base_instructions = f"The lyrics for this song are missing (it might be an instrumental track). Sardonically roast the user for listening to such an obscure or wordless track. Use SIMPLE English. MAXIMUM 40 WORDS."
    else:
        base_instructions = """Analyze the user's vibe based on this song. 
        CRITICAL RULES:
        1. MUST reference or twist at least one lyric.
        2. MUST reuse 2-5 exact words from the lyrics.
        3. Be conversational, informal, and highly aggressive.
        4. Use biting insults. Avoid generic words like 'garbage' or 'trash'.
        5. Use SIMPLE English. MAXIMUM 40 WORDS."""

    # Grounding instructions if interaction exists
    grounding = f"\n### USER PSYCHOLOGY (HIGH PRIORITY)\nThe user {interaction_state}. Use this to influence the confidence and aggressive framing of your roast. If they confirmed, double down on the insult. If they denied, sardonically mock their lack of self-awareness." if interaction_state else ""

    metadata_context = f"Vibe: {emotions_str}"
    lyrics_section = f"### LYRICS\n{lyrics}" if lyrics_found else "### LYRICS\n[LYRICS NOT FOUND: SONG TOO OBSCURE]"

    return f"""{base_instructions}{grounding}{joke_instruction}

### DATA
Track: "{track}" by {artist}
{metadata_context}

{lyrics_section}

### ROLE (STRICT)
You are {persona_desc}.
{persona_style}
You MUST think and speak like this persona. 
Use vocabulary, analogies, or observations from this field.

Start immediately with the roast. No setup."""

# ==========================
# CORE GENERATION (RAW DRAFT - PASS 1)
# ==========================
def _generate_roast_raw(song: Dict, persona: str = "normal", custom_prompt: str = None, interaction_state: str = None) -> str:
    """
    Pass 1: Generate the raw, unfiltered roast draft.
    """
    prompt = build_prompt(song, persona, custom_prompt, interaction_state)
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            top_p=0.9,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Pass 1 Draft Error: {str(e)}")
        return "You listen to this and expect a compliment? Please."

# ==========================
# PROMPT BUILDER (PROFILE)
# ==========================
def build_profile_prompt(songs: List[Dict], persona: str = "normal", custom_prompt: str = None, interaction_state: str = None) -> str:
    summary = []
    all_emotions = []
    all_artists = []
    
    for s in songs:
        emotions = s.get("Emotion", [])
        all_emotions.extend(emotions)
        all_artists.append(s.get('artist_name'))
        summary.append(f"- {s.get('track_name')} by {s.get('artist_name')} ({', '.join(emotions)})")
    
    top_artists = list(set(all_artists))[:3]
    unique_emotions = list(set(all_emotions))[:3]
    
    persona_info = PERSONAS.get(persona, PERSONAS["normal"])
    persona_desc = persona_info["desc"]
    persona_style = persona_info["style"]

    # Use custom prompt if provided, otherwise use default savage profile template
    base_instructions = custom_prompt if custom_prompt else f"""Analyze this user's overall music taste with a sharp, judgmental tone. 
Briefly mention artists like {', '.join(top_artists)} and detect their emotional patterns ({', '.join(unique_emotions)}).
Use SIMPLE English. MAXIMUM 40 WORDS."""

    # Grounding instructions if interaction exists
    grounding = f"\n### GROUNDING (HIGH PRIORITY)\nThe user {interaction_state}. You MUST weave this into the profile analysis naturally." if interaction_state else ""

    return f"""{base_instructions}{grounding}

### DATA (RECENT HISTORY)
{chr(10).join(summary)}

### ROLE (STRICT)
You are {persona_desc}.
{persona_style}
You MUST think and speak like this persona.

Start immediately with the profile roast. No setup."""


# ==========================
# CORE GENERATION (PROFILE DRAFT - PASS 1)
# ==========================
def _generate_profile_roast_raw(songs: List[Dict], persona: str = "normal", custom_prompt: str = None, interaction_state: str = None) -> str:
    """
    Pass 1: Generate the raw profile roast draft.
    """
    prompt = build_profile_prompt(songs, persona, custom_prompt, interaction_state)
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            top_p=0.9,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Profile Pass 1 Draft Error: {str(e)}")
        return f"I see songs from {', '.join([s.get('artist_name') for s in songs[:2]])}... I have no words."

# ==========================
# CORE GENERATION (PROFILE STREAMING - PASS 2)
# ==========================
def generate_profile_roast_stream(songs: List[Dict], persona: str = "normal", custom_prompt: str = None, interaction_state: str = None) -> Generator[str, None, None]:
    """
    Pass 2: Rewrite the profile roast to be more natural and grounded.
    """
    # Step 1: Get raw draft
    raw_text = _generate_profile_roast_raw(songs, persona, custom_prompt, interaction_state)
    
    # Step 2: Build Rewrite Prompt
    grounding_reminder = f"\n- MANDATORY: Incorporate the meaning of the user's previous response ({interaction_state}) naturally into the text." if interaction_state else ""
    
    rewrite_prompt = f"""
Rewrite this overall music profile roast to sound more natural, spontaneous, and less repetitive.

RULES:
- remove repeated phrasing
- vary sentence structure
- keep meaning the same{grounding_reminder}
- make it sound human and direct
- MAXIMUM 40 WORDS. 2-3 sentences.

TEXT:
"{raw_text}"

Start immediately with the refined profile roast."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": rewrite_prompt}],
            temperature=0.8,
            top_p=1.0,
            stream=True,
            max_tokens=150
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
                    
    except Exception as e:
        logger.error(f"Groq Profile Rewrite Stream Error: {str(e)}")
        yield raw_text # Fallback to raw draft


# ==========================
# CORE GENERATION (STREAMING REWRITE - PASS 2)
# ==========================
def generate_roast_stream(song: Dict, persona: str = "normal", custom_prompt: str = None, interaction_state: str = None) -> Generator[str, None, None]:
    """
    Pass 2: Take the raw draft and rewrite it to be more natural and less repetitive.
    Streams the final result to the UI.
    """
    # Step 1: Get the raw draft in the background (Pass 1)
    raw_text = _generate_roast_raw(song, persona, custom_prompt, interaction_state)
    
    # Step 2: Build the Editor Rewrite Prompt (Pass 2)
    # Ensure the rewrite phase knows about the grounding so it doesn't strip it.
    grounding_reminder = f"\n- MANDATORY: Incorporate the meaning of the user's previous response ({interaction_state}) naturally into the text." if interaction_state else ""
    
    rewrite_prompt = f"""
Rewrite the following music roast to sound more natural, spontaneous, and less repetitive.

RULES:
- remove repeated phrasing or patterns such as "stuck on"
- vary sentence structure
- keep meaning the same{grounding_reminder}
- make it sound human
- MAXIMUM 40 WORDS. 2-3 sentences.

TEXT:
"{raw_text}"

Start immediately with the refined roast."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": rewrite_prompt}],
            temperature=0.7,
            top_p=1.0,
            stream=True,
            max_tokens=150
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
                    
    except Exception as e:
        logger.error(f"Groq Rewrite Stream Error (Roast): {str(e)}")
        yield f"[REWRITE ERROR: {str(e)}]"


# ==========================
# CORE GENERATION (BATCH)
# ==========================
def generate_roast(song: Dict, persona: str = "normal", custom_prompt: str = None) -> str:
    prompt = build_prompt(song, persona, custom_prompt)
    
    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
            top_p=0.9,

            max_tokens=150
        )
        return response.choices[0].message.content.strip()
            
    except Exception as e:
        logger.error(f"Groq Batch Error: {str(e)}")
        return "I'm too offended by your taste to even speak right now."


# ==========================
# CORE GENERATION (FINAL VERDICT)
# ==========================
def generate_final_verdict(songs: List[Dict], persona: str = "normal") -> str:
    summary = []
    for s in songs:
        emotions = ", ".join(s.get("Emotion", []))
        summary.append(f"- {s.get('track_name')} ({emotions})")
    
    songs_list = "\n".join(summary)
    persona_info = PERSONAS.get(persona, PERSONAS["normal"])
    persona_desc = persona_info["desc"]

    prompt = f"""Give a final, simple, and funny verdict on the user's life. 
Use BASIC English. MAXIMUM 15 WORDS. STRICTLY ONE SENTENCE.

### HISTORY
{songs_list}

### RULES
1. PERSONA: You are {persona_desc}.
2. TASK: Give a FINAL verdict on the user. Mention things like their inability to fold laundry, spending $50 on takeout, or their messy desk.
3. NO MUSIC INSULTS: Strictly roast the user, not the songs.
4. WORDS: Simple, short words only. No big vocabulary.

Start now."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
            top_p=0.9,

            max_tokens=50
        )
        return response.choices[0].message.content.strip()
            
    except Exception as e:
        logger.error(f"Groq Batch Error (Verdict): {str(e)}")
        return "You're a lost cause. Truly."


# ==========================
# CORE GENERATION (FINAL VERDICT OPTIMIZED - PASS 1)
# ==========================
def _generate_final_verdict_raw(songs: List[Dict], persona: str = "normal", collection_name: str = "your collection") -> str:
    """
    Pass 1: Generates the raw final verdict draft based on analysis history.
    """
    summary_data = []
    for s in songs:
        track = s.get("track_name", "Unknown")
        roast_snippet = s.get("roast", "No roast generated")[:100]
        emotions = ", ".join(s.get("Emotion", ["neutral"]))
        summary_data.append(f"Track: {track} | Vibe: {emotions} | Analysis: {roast_snippet}")

    history = "\n".join(summary_data)
    persona_info = PERSONAS.get(persona, PERSONAS["normal"])
    persona_desc = persona_info["desc"]

    prompt = f"""Based on the following music analysis history from the collection "{collection_name}", give a FINAL, brutal, and simple verdict on the user's life. 
Use BASIC English. MAXIMUM 20 WORDS. STRICTLY ONE SENTENCE.

### ANALYSIS HISTORY
{history}

### RULES
1. PERSONA: You are {persona_desc}.
2. TASK: Summarize their life choices based on the analysis snippets provided. Mention one pathetic habit (like ordering pizza at 3 AM or having 500 unread emails).
3. NO MUSIC INSULTS: Roast the user, not the art.
4. WORDS: Simple, short words only.

Start now."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.0,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Pass 1 Verdict Error: {str(e)}")
        return "You're a lost cause. Truly."

# ==========================
# CORE GENERATION (FINAL VERDICT STREAMING - PASS 2)
# ==========================
def generate_final_verdict_stream(songs: List[Dict], persona: str = "normal", collection_name: str = "your collection") -> Generator[str, None, None]:
    """
    Pass 2: Refines the raw verdict draft and streams it.
    """
    raw_verdict = _generate_final_verdict_raw(songs, persona, collection_name)
    
    rewrite_prompt = f"""
Rewrite this final music verdict to be more impactful, funny, and naturally conversational.

RULES:
- Make it flow better
- Keep the persona consistent
- Keep it under 20 words
- STRICTLY ONE SENTENCE

TEXT:
"{raw_verdict}"

Start immediately with the refined verdict."""

    try:
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": rewrite_prompt}],
            temperature=0.7,
            top_p=1.0,
            stream=True,
            max_tokens=100
        )
        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        logger.error(f"Verdict Rewrite Error: {str(e)}")
        yield raw_verdict # Fallback to raw draft
