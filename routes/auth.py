# app/routes/auth.py

from datetime import datetime
import re

from flask import Blueprint, redirect, request, jsonify, session
from services.emotion import process_song_emotion, process_emotions_batch
from services.processing import process_songs_batch
from services.cache import redis_client_raw, cache_get, cache_set
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.cache_handler import RedisCacheHandler
import spotipy
import requests
import os
import logging
import random
import time
import uuid

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

# ==========================
# DEBUG HELPER
# ==========================
def debug_spotify_request(method_name, sp, *args, **kwargs):
    """
    Wraps Spotify API calls with detailed logging for debugging.
    """
    is_vercel = os.getenv("VERCEL") == "1" or os.getenv("VERCEL_ENV") is not None
    env = "vercel" if is_vercel else "local"
    
    # Check if token_info was passed explicitly (for workers)
    token_info = kwargs.pop('debug_token_info', None)
    
    # Attempt to get token info from session if not provided
    if not token_info:
        try:
            sp_oauth = create_spotify_oauth()
            token_info = sp_oauth.cache_handler.get_cached_token()
        except Exception:
            pass

    # Fallback: try to get token from the sp object itself
    access_token = "N/A"
    if hasattr(sp, 'auth') and sp.auth:
        access_token = sp.auth
    elif hasattr(sp, 'auth_manager') and hasattr(sp.auth_manager, 'get_cached_token'):
        t = sp.auth_manager.get_cached_token()
        if t: access_token = t.get('access_token', 'N/A')
    
    if access_token == "N/A" and token_info:
        access_token = token_info.get("access_token", "N/A")

    scopes = token_info.get("scope", "N/A") if token_info else "N/A"
    
    def mask_token(t):
        if not t or t == "N/A": return "N/A"
        if len(t) < 15: return t
        return f"{t[:7]}...{t[-4:]}"

    # Mapping methods to endpoints for clearer logs
    mapping = {
        "playlist_items": ("GET", "https://api.spotify.com/v1/playlists/{}/items"),
        "current_user_saved_tracks": ("GET", "https://api.spotify.com/v1/me/tracks"),
        "current_user_playlists": ("GET", "https://api.spotify.com/v1/me/playlists"),
        "playlist": ("GET", "https://api.spotify.com/v1/playlists/{}"),
        "current_user_top_tracks": ("GET", "https://api.spotify.com/v1/me/top/tracks"),
        "current_user": ("GET", "https://api.spotify.com/v1/me"),
    }
    
    http_method, url_template = mapping.get(method_name, ("UNKNOWN", "https://api.spotify.com/v1/..."))
    
    url = url_template
    if "{}" in url_template:
        if len(args) > 0:
            url = url_template.format(args[0])
        elif 'playlist_id' in kwargs:
            url = url_template.format(kwargs['playlist_id'])

    # LOGGING
    log_header = f"\n[SPOTIFY REQUEST] [{env.upper()}]"
    log_body = (
        f"METHOD: {http_method}\n"
        f"URL: {url}\n"
        f"PARAMS: {kwargs}\n"
        f"SCOPES: {scopes}\n"
        f"TOKEN: {mask_token(access_token)}"
    )
    logger.info(f"{log_header}\n{log_body}")
    
    try:
        func = getattr(sp, method_name)
        result = func(*args, **kwargs)
        logger.info(f"[SPOTIFY SUCCESS] {method_name} call completed. TOKEN_USED: {mask_token(access_token)}")
        return result
    except Exception as e:
        status = getattr(e, 'http_status', 'UNKNOWN')
        # Improved error body capture
        body = "N/A"
        if hasattr(e, 'msg'):
            body = e.msg
        elif hasattr(e, 'args') and len(e.args) > 0:
            body = str(e.args[0])
            
        # For SpotifyException, we can often get more details
        if hasattr(e, 'headers'):
            logger.debug(f"Error Headers: {e.headers}")
            
        err_msg = (
            f"\n[SPOTIFY ERROR] [{env.upper()}]\n"
            f"STATUS: {status}\n"
            f"BODY: {body}\n"
            f"METHOD: {http_method}\n"
            f"URL: {url}\n"
            f"TOKEN_USED: {mask_token(access_token)}"
        )
        if method_name == "playlist_items" and len(args) > 0:
            err_msg += f"\nPLAYLIST_ID: {args[0]}"
            
        logger.error(err_msg)
        raise e

# ==========================
# ENV CONFIG (IMPORTANT)
# ==========================
def get_spotify_config():
    """Lazily fetch Spotify config to ensure env vars are loaded."""
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or os.getenv("SPOTIPY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or os.getenv("SPOTIPY_CLIENT_SECRET")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI") or os.getenv("SPOTIPY_REDIRECT_URI") or "http://127.0.0.1:8000/callback"
    
    if not client_id or not client_secret:
        logger.error(f"MISSING SPOTIFY CREDENTIALS: ID={bool(client_id)}, Secret={bool(client_secret)}")
    
    return client_id, client_secret, redirect_uri

LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")

# Comprehensive scopes for all playlist/library access
SCOPE = "user-top-read playlist-read-private playlist-read-collaborative user-library-read playlist-modify-public playlist-modify-private user-read-private"


# ==========================
# SPOTIFY AUTH SETUP
# ==========================
def create_spotify_oauth():
    client_id, client_secret, redirect_uri = get_spotify_config()
    
    # Ensure a unique cache ID exists for this session
    if 'cache_id' not in session:
        session['cache_id'] = str(uuid.uuid4())
    
    cache_key = f"spotify_token:{session['cache_id']}"
    cache_handler = RedisCacheHandler(redis_client_raw, key=cache_key)
    
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        cache_handler=cache_handler,
        show_dialog=True
    )

# ==========================
# LOGIN ROUTE
# ==========================
@auth_bp.route("/login")
def login():
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


# ==========================
# CALLBACK ROUTE
# ==========================
@auth_bp.route("/callback")
def callback():
    sp_oauth = create_spotify_oauth()
    code = request.args.get("code")
    
    if not code:
        logger.error("No code provided in callback")
        return redirect("/")

    # check_cache=False ensures we exchange the NEW code instead of trying 
    # to refresh an old/invalid token that might be in Redis.
    try:
        sp_oauth.get_access_token(code, check_cache=False)
        logger.info("Successfully acquired new access token.")
    except Exception as e:
        logger.error(f"Failed to get access token: {e}")
        return f"Authentication Error: {str(e)}. Please check your SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET.", 500
        
    return redirect("/")


# ==========================
# AUTH HELPERS
# ==========================
# Create a shared session with an increased connection pool to handle parallel workers
spotify_session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
spotify_session.mount("https://", adapter)
spotify_session.mount("http://", adapter)

def get_sp_client(timeout=10):
    sp_oauth = create_spotify_oauth()
    try:
        token = sp_oauth.cache_handler.get_cached_token()
        if not token:
            return None
            
        # sp_oauth will handle refreshing if needed when we call methods,
        # but we can explicitly refresh if expired to ensure the cache is updated.
        if sp_oauth.is_token_expired(token):
            logger.info("Token expired. Refreshing...")
            token = sp_oauth.refresh_access_token(token['refresh_token'])
            
        if not sp_oauth.validate_token(token):
            return None
            
        # Return client with the refreshed token and shared session
        return spotipy.Spotify(
            auth=token['access_token'], 
            requests_timeout=timeout,
            requests_session=spotify_session
        )
    except Exception as e:
        logger.error(f"Failed to initialize Spotify client: {e}")
        return None

@auth_bp.route("/debug-token")
def debug_token():
    sp_oauth = create_spotify_oauth()
    token_info = sp_oauth.cache_handler.get_cached_token()
    if not token_info:
        return jsonify({
            "status": "no token found",
            "cache_key": f"spotify_token:{session.get('cache_id')}",
            "session_keys": list(session.keys())
        })
    
    return jsonify({
        "status": "authenticated",
        "active_scopes": token_info.get("scope", "unknown"),
        "expires_at": token_info.get("expires_at"),
        "is_expired": token_info.get("expires_at", 0) < datetime.now().timestamp(),
        "cache_id": session.get('cache_id')
    })

@auth_bp.route("/logout")
def logout():
    # If we want to be thorough, we could delete the spotify_token from Redis here
    # but clearing the session is enough as the user loses their cache_id.
    session.clear()
    return redirect("/")


@auth_bp.route("/auth-status")
def auth_status():
    sp = get_sp_client()
    return jsonify({
        "authenticated": sp is not None
    })

@auth_bp.route("/get-user-top-tracks")
def get_user_top_tracks():
    sp = get_sp_client()
    if not sp: return jsonify({"error": "not logged in"}), 401

    try:
        results = debug_spotify_request("current_user_top_tracks", sp, limit=5, time_range='medium_term')
        tracks = []
        for t in results['items']:
            tracks.append({
                "name": t['name'],
                "artist": t['artists'][0]['name'],
                "image": t['album']['images'][0]['url'] if t['album']['images'] else ""
            })
        return jsonify({"tracks": tracks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route("/me")
def get_user():
    sp = get_sp_client()
    if not sp: return jsonify({"error": "not logged in"}), 401
    user = debug_spotify_request("current_user", sp)
    images = user.get("images", [])
    image_url = images[0]["url"] if images else None
    return jsonify({
        "display_name": user.get("display_name", "User"),
        "image": image_url
    })

import concurrent.futures

@auth_bp.route("/get-collections")
def get_collections():
    # Use a slightly longer timeout for Vercel stability
    sp = get_sp_client(timeout=10)
    if not sp: return jsonify({"error": "Not authenticated"}), 401

    try:
        # Get user_id and check limit
        user = debug_spotify_request("current_user", sp)
        user_id = user.get('id')
        session['user_id'] = user_id

        from services.cache import has_reached_limit
        if has_reached_limit(user_id):
            return jsonify({
                "error": "limit_reached",
                "message": "You've already performed your one-time analysis. Come back in your next life."
            }), 403

        # Get token info for logging purposes in debug_spotify_request

        liked_total = 0
        try:
            liked_res = debug_spotify_request("current_user_saved_tracks", sp, limit=1)
            liked_total = liked_res.get('total', 0)
        except: pass

        # Fetch playlists
        playlists_res = debug_spotify_request("current_user_playlists", sp, limit=50)
        items = playlists_res.get('items', []) if playlists_res else []

        def process_playlist(p):
            if not p: return None

            p_id = p.get('id')
            p_name = p.get('name')
            
            # 1. Check initial count
            tracks_info = p.get('tracks', {})
            initial_count = 0
            if isinstance(tracks_info, dict):
                initial_count = tracks_info.get('total', 0) or 0
            
            total_tracks = initial_count
            logger.info(f"[DIAGNOSTIC] Playlist: {p_name} | Initial Count: {initial_count}")

            # 2. Safety Fallback: Trigger if initial is 0
            if initial_count == 0:
                try:
                    # We'll try the items endpoint with limit 1 - it's often more reliable for counts
                    check = debug_spotify_request(
                        "playlist_items", 
                        sp, 
                        p_id, 
                        limit=1,
                        debug_token_info=token_info
                    )
                    if check and isinstance(check, dict):
                        total_tracks = check.get('total', 0) or 0
                        logger.info(f"[DIAGNOSTIC] Fallback Result for {p_name}: {total_tracks}")
                except Exception as e:
                    logger.debug(f"[DIAGNOSTIC] Fallback Failed for {p_name}: {e}")

            # Defensive image parsing
            image_url = ""
            if p.get('images') and len(p.get('images')) > 0:
                img = p.get('images')[0]
                if isinstance(img, dict) and img.get('url'):
                    image_url = img.get('url')

            owner_id = p.get('owner', {}).get('id')
            is_owner = owner_id == user_id
            is_collaborative = p.get('collaborative', False)

            return {
                "id": p_id,
                "name": p_name,
                "image": image_url,
                "total": total_tracks,
                "is_owner": is_owner,
                "is_collaborative": is_collaborative
            }

        # Use ThreadPoolExecutor to process playlists in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(process_playlist, items))

        # Filter out None results and playlists with 0 tracks
        playlists = [r for r in results if r is not None and r.get('total', 0) > 0]
        
        # FINAL LOGGING OF THE WHOLE BATCH
        summary = {p['name']: p['total'] for p in playlists}
        logger.info(f"[DIAGNOSTIC] FINAL COLLECTION SUMMARY: {summary}")

        return jsonify({
            "liked_total": liked_total,
            "playlists": playlists
        })
    except Exception as e:
        logger.error(f"Collections fetch error: {e}")
        return jsonify({"error": str(e)}), 500



def clean_track_name(name: str) -> str:
    """Removes junk like (Remastered) or - Live from track names."""
    # 1. Remove everything in parentheses or brackets (e.g. "(feat. ...)", "[Remix]")
    name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name)

    # 2. Remove common suffixes after a hyphen (Remastered, Live, etc.)
    # We use a broader regex to catch variations
    name = re.sub(r'\s*-\s*(Remastered|Live|Radio Edit|Deluxe Edition|Single Version|Mix|Edit|Version|feat\..*|with.*).*', '', name, flags=re.I)

    # 3. Final trim
    return name.strip()

def extract_valid_tracks(items):
    """
    STRICT LOGIC: Extract valid track objects from Spotify response items.
    Filters out None, missing data, and local files.
    """
    valid_tracks = []
    for entry in items:
        # Spotify playlist items wrap the track in 'track' or 'item'
        track = entry.get('track') or entry.get('item')

        if not track:
            continue

        # Ignore local files as they lack stable IDs/metadata for enrichment
        if track.get('is_local'):
            continue

        valid_tracks.append(track)

    return valid_tracks

@auth_bp.route("/fetch-collection-songs", methods=["POST"])
def fetch_collection_songs():
    sp = get_sp_client()
    if not sp: return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    col_id = data.get("collection_id")
    col_name = data.get("collection_name")

    _, _, redirect_uri = get_spotify_config()
    logger.info(f"FETCHING SONGS: Collection '{col_name}' (ID: {col_id})")
    logger.info(f"REDIRECT_URI_USED: {redirect_uri}")
    try:
        if col_id == "liked":
            pl = debug_spotify_request("current_user_saved_tracks", sp, limit=50)
        else:
            pl = debug_spotify_request("playlist_items", sp, col_id, limit=50)
            
        if not pl:
            logger.error("Spotify API returned None for the collection.")
            return jsonify({"error": "spotify_error", "message": "Spotify returned no data."}), 500

        items = pl.get('items', [])
        raw_tracks = extract_valid_tracks(items)
        count = len(raw_tracks)
        
        logger.info(f"FETCH_DEBUG: Received {len(items)} items. Valid tracks: {count}")
        
        if count == 0:
            logger.warning(f"Collection '{col_name}' has no usable tracks.")
            return jsonify({
                "error": "empty_collection", 
                "message": f"Spotify says your '{col_name}' collection has no usable tracks (local files are ignored)."
            }), 400

        if len(items) > 0:
            # DEEP DUMP of the first item so we can see the exact structure in Vercel logs
            logger.info(f"RAW_ITEM_DUMP (FIRST): {str(items[0])[:1000]}...")

        # We already have raw_tracks filtered by extract_valid_tracks
        # But we still need to ensure they have names and artists for enrichment
        processed_tracks = []
        for index, track_obj in enumerate(raw_tracks):
            t_name = track_obj.get('name')
            t_artists = track_obj.get('artists', [])
            
            if t_name and isinstance(t_artists, list) and len(t_artists) > 0:
                processed_tracks.append(track_obj)
            else:
                logger.warning(f"Parser skipped track at index {index}: {t_name or 'No Name'}. Type: {track_obj.get('type', 'unknown')}")

        if not processed_tracks:
            logger.error(f"Failed to parse any usable tracks from {count} candidates.")
            return jsonify({
                "error": "no_songs_found", 
                "message": f"Found {count} tracks, but none had valid metadata (name/artist)."
            }), 400

        random.shuffle(processed_tracks)
        selected_tracks = processed_tracks[:10]

        songs = []
        for track in selected_tracks:
            original_name = track.get("name", "Unknown Track")
            track_name = clean_track_name(original_name)
            artists_list = track.get("artists", [])
            artists = ", ".join([a.get("name", "Unknown Artist") for a in artists_list])
            primary_artist = artists_list[0].get("name", "Unknown Artist") if artists_list else "Unknown Artist"
            
            album = track.get("album", {})
            album_name = album.get("name", "Unknown Album")
            album_image = album.get("images", [])[0].get("url", "") if album.get("images") else ""

            lastfm = get_lastfm_track_info(primary_artist, track_name)
            sarcasm = decide_sarcasm_params(lastfm["tags"], lastfm["playcount"])

            songs.append({
                "track_name": track_name,
                "artist_name": artists,
                "album_name": album_name,
                "album_image": album_image,
                "playcount": lastfm["playcount"],
                "tags": lastfm["tags"],
                "sarcasm_level": sarcasm["level"],
                "sarcasm_type": sarcasm["type"],
                "target": sarcasm["target"]
            })

        return jsonify({
            "collection_name": col_name,
            "total": len(songs),
            "data": songs
        })
    except Exception as e:
        logger.error(f"Fetch Songs Error: {e}")
        return jsonify({"error": str(e)}), 500

# ==========================
# LAST.FM ENRICHMENT
# ==========================
def get_lastfm_track_info(artist, track):
    cache_key = f"lastfm:{artist}:{track}".lower()
    cached = cache_get(cache_key)
    if cached:
        return cached

    url = "http://ws.audioscrobbler.com/2.0/"
    params = {
        "method": "track.getInfo",
        "api_key": LASTFM_API_KEY,
        "artist": artist,
        "track": track,
        "autocorrect": 1,
        "format": "json"
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if "error" in data: return {"tags": [], "playcount": 0}
        track_info = data.get("track", {})
        playcount = int(track_info.get("playcount", 0))
        tags_data = track_info.get("toptags", {}).get("tag", [])
        if isinstance(tags_data, dict): tags_data = [tags_data]
        tags = [t["name"].lower() for t in tags_data if "name" in t]
        
        result = {"tags": tags, "playcount": playcount}
        cache_set(cache_key, result, ex=86400) # Cache for 1 day
        return result
    except:
        return {"tags": [], "playcount": 0}

# ==========================
# SARCASM MAPPING
# ==========================
def decide_sarcasm_params(tags, playcount):
    tags_str = " ".join(tags)
    if any(g in tags_str for g in ["classical", "jazz", "orchestra"]):
        return {"level": 2, "type": "dry", "target": "situation"}
    if any(g in tags_str for g in ["boy band", "teen pop", "eurodance"]):
        return {"level": 3, "type": "playful", "target": "self"}
    if any(g in tags_str for g in ["sad", "emo", "melancholy"]):
        return {"level": 0, "type": "none", "target": "none"}
    if playcount > 5_000_000:
        return {"level": 5, "type": "exaggerated", "target": "situation"}
    return {"level": 2, "type": "witty", "target": "situation"}


@auth_bp.route("/fetch-lyrics", methods=["POST"])
def fetch_lyrics():
    songs = request.json.get("songs", [])
    enriched = process_songs_batch(songs)
    # Parallelized emotion analysis
    final_data = process_emotions_batch(enriched)
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "total_songs": len(final_data),
        "songs_with_lyrics": len([s for s in final_data if s.get("lyrics_found")]),
        "data": final_data
    })
