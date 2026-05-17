# CONTACT SAMARTHRAWAT18@GMAIL.COM FOR USING THE PROJECT AS SPOTIFY HAS RATE LIMITS ON DEVELOPMENT MODE APIS, EACH USAGE NEED EMAIL-ID TO BE ADDED BY THE API ADMINISTRATOR FROM THE SPOTIFY DASHBOARD.

# 🐱 CRITIC_OS // Sarcastic Music Analyzer

**CRITIC_OS** is a high-performance, AI-driven web application that analyzes your Spotify library and provides brutally honest, sarcastic critiques of your music taste. Built for the modern "audio-elitist," it transforms your listening habits into a series of savage roasts delivered by multiple distinct AI personas.

![CRITIC_OS Banner](https://placehold.co/1200x400/0a0a0a/00ff41?text=CRITIC_OS+v1.2.0)

## 🚀 Key Features

*   **Multimodal Roasting:** Choose from 6 distinct AI personas (Normal, Cat, Grandpa, Valley Girl, Gordon Ramsay, and Cyberpunk Hacker).
*   **Deep Context Analysis:** Integrates **Last.fm** metadata to distinguish between "mainstream basic" and "pretentious hipster" tastes.
*   **Parallel Enrichment Engine:** High-speed pipeline that fetches lyrics and runs emotion detection (HuggingFace) in parallel, processing playlists in < 6 seconds.
*   **Continuous Streaming:** Real-time AI response generation using **Groq (Llama-3.3)** for an immersive terminal-like experience.
*   **Interactive Sessions:** AI asks follow-up questions that dynamically re-ground the roast based on your answers.
*   **Production Hardened:** Optimized for Vercel Serverless with Redis-backed session management and surgical memory usage.

## 🛠️ Tech Stack

*   **Backend:** Flask (Python)
*   **AI/LLM:** Groq (Llama-3.3-70B), HuggingFace (Emotion Classification)
*   **Data APIs:** Spotify (Spotipy), Last.fm, LRC_LIB (Lyrics)
*   **Database/Cache:** Redis (Upstash)
*   **Deployment:** Vercel

## ⚙️ Environment Variables

To run CRITIC_OS locally or in production, you need the following:

```env
# Spotify API
SPOTIPY_CLIENT_ID=your_id
SPOTIPY_CLIENT_SECRET=your_secret
SPOTIPY_REDIRECT_URI=http://localhost:5000/callback

# AI & Enrichment
GROQ_API_KEY=your_key
HUGGINGFACE_TOKEN=your_token
LASTFM_API_KEY=your_key

# Infrastructure
REDIS_URL=redis://...
SECRET_KEY=your_flask_secret
```

## 📦 Deployment

### 1. Vercel
The project is configured with `vercel.json`. Simply connect your GitHub repo and add the environment variables.

### 2. Hugging Face Spaces (Recommended)
1. Create a new **Docker Space** on Hugging Face.
2. Upload all files (or connect your GitHub).
3. Add the environment variables in the **Settings** tab.
4. The app will automatically build using the provided `Dockerfile` and run on port 7860.

### 3. Redis
Required for session persistence. Use **Upstash Redis** (external) for the best compatibility with both Vercel and HF Spaces.

## 📜 License

© 2026 CRITIC_OS // ALL RIGHTS RESERVED.
*This project is for satirical and educational purposes.*
