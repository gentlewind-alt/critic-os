# CRITIC_OS Flask Web App - Routes Structure

This is a complete Flask web app scaffold for the Sarcastic Music Analyzer with placeholder routes ready for your logic.

## Project Structure

```
Sarcastic Music Analyzer/
├── app.py                      # Main Flask app factory
├── config.py                   # Configuration (Spotify API keys, model paths)
├── requirements.txt            # Python dependencies
├── main.ipynb                  # Your existing Jupyter notebook
│
├── routes/
│   ├── __init__.py
│   ├── landing.py             # Landing page & OAuth login (GET /, /login, /callback)
│   ├── analysis.py            # Main analysis dashboard & API (GET /analyze, /api/songs, etc)
│   └── api.py                 # Utility endpoints (POST /api/lyrics, /api/emotions, etc)
│
├── services/
│   ├── __init__.py
│   └── services.py            # PLACEHOLDER: Add your business logic here
│
├── templates/
│   ├── landing.html           # Home page (replace with CRITIC_OS_Landing_Page.html)
│   └── analysis.html          # Dashboard (replace with CRITIC_OS_Analysis_Page.html)
│
├── static/
│   ├── css/                   # CSS files
│   ├── js/                    # JavaScript files
│   └── images/                # Downloaded PNG images
└── .env                       # Environment variables (create this)
```

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Create .env file
```
FLASK_ENV=development
SECRET_KEY=your-secret-key-here
```

### 3. Run the app
```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

## Routes Overview

### Landing Page (`routes/landing.py`)
- `GET /` → Landing page
- `GET /login` → Redirect to Spotify OAuth
- `GET /callback` → Handle Spotify OAuth callback
- `GET /logout` → Clear session
- `GET /status` → Check authentication status

### Analysis Page (`routes/analysis.py`)
- `GET /analyze` → Main dashboard (requires auth)
- `GET /api/songs` → Fetch all processed songs (AJAX)
- `GET /api/songs/<track_id>/roast` → Generate roast for specific track
- `GET /api/songs/<track_id>/emotions` → Get emotions for track
- `POST /api/process-songs` → Trigger full processing pipeline

### Utility APIs (`routes/api.py`)
- `GET /api/health` → Health check
- `GET /api/config` → Public config
- `POST /api/lyrics` → Fetch lyrics for a track
- `POST /api/emotions` → Detect emotions from text
- `GET /api/lastfm/<artist>/<track>` → Get Last.fm enrichment data

## PLACEHOLDER Logic to Implement

Each route has detailed comments indicating where to add your logic. Key areas:

### 1. **OAuth Callback** (`routes/landing.py::callback()`)
From your `main.ipynb`:
- Use `setup_spotify_auth()` to exchange code for token
- Store `token_info` in `session`

### 2. **Fetch Top Songs** (`routes/analysis.py::get_songs()`)
From your `main.ipynb`:
- Call `fetch_top_songs(sp, limit=10)`
- Enrich with `get_lastfm_track_info()` and `decide_sarcasm_params()`
- Cache in session

### 3. **Fetch Lyrics** (`routes/api.py::fetch_lyrics()`)
From your `main.ipynb`:
- Use `LyricFetcher().get_lyrics()` to fetch lyrics
- Return JSON response

### 4. **Detect Emotions** (`routes/api.py::detect_emotions()`)
From your notebook:
- Load emotion model via `load_model()`
- Call `predict_emotions()` on lyrics
- Return emotions dict

### 5. **Generate Roasts** (`routes/analysis.py::generate_roast_for_track()`)
From your notebook:
- Load Mistral model locally
- Build prompt with sarcasm parameters
- Call model and return generated text

## Services Layer Structure

Create these in `services/`:

```python
# services/spotify_service.py
class SpotifyService:
    @staticmethod
    def fetch_top_tracks(sp, limit=10):
        # From main.ipynb::fetch_top_songs()
        pass

# services/lyrics_service.py
class LyricsService:
    @staticmethod
    def fetch_lyrics(track_name, artist_name):
        # From main.ipynb::LyricFetcher
        pass

# services/emotion_service.py
class EmotionService:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        # Singleton pattern to load model once
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

# services/roast_service.py
class RoastService:
    @staticmethod
    def generate_roast(song_data, emotions, sarcasm_params):
        # From main.ipynb::generate_sarcasm()
        pass

# services/lastfm_service.py
class LastFmService:
    @staticmethod
    def get_track_info(artist, track):
        # From main.ipynb::get_lastfm_track_info()
        pass
```

## HTML Templates

Replace the placeholder templates with your downloaded Stitch files:

1. `templates/landing.html` ← Replace with `CRITIC_OS_Landing_Page.html`
2. `templates/analysis.html` ← Replace with `CRITIC_OS_Analysis_Page.html`

Update image paths in HTML:
```html
<img src="{{ url_for('static', filename='images/image1.png') }}" alt="Design">
```

Update button links:
```html
<a href="{{ url_for('landing.login') }}" class="btn">Login</a>
```

## Session Management

The app uses Flask sessions to store:
- `session['token_info']` - Spotify OAuth token
- `session['user_id']` - User's Spotify ID
- `session['processed_songs']` - Cached song data

Set `SESSION_PERMANENT = True` in config.py to persist sessions.

## Next Steps

1. ✅ Routes structure created with placeholders
2. ⏳ Add service layer logic from main.ipynb
3. ⏳ Replace HTML templates with Stitch files
4. ⏳ Implement emotion detection integration
5. ⏳ Integrate Mistral roast generation
6. ⏳ Add caching for performance
7. ⏳ Deploy to production

## Notes

- All Spotify API credentials are in `config.py`
- Model paths must exist before running
- Use `@landing_bp.before_request` to validate tokens
- Implement error handling with try/except blocks
- Log errors for debugging

Good luck with your sarcastic music analyzer! 🎵
