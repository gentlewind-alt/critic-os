# app/routes/auth.py

from datetime import datetime
import re

from flask import Blueprint, redirect, request, jsonify, session
from services.emotion import process_song_emotion
from services.processing import process_songs_batch
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
from spotipy.cache_handler import FlaskSessionCacheHandler
import spotipy
import requests
import os
import logging
import random

auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)

# ==========================
# ENV CONFIG (IMPORTANT)
# ==========================
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")

# Comprehensive scopes for all playlist/library access
SCOPE = "user-top-read playlist-read-private playlist-read-collaborative user-library-read playlist-modify-public playlist-modify-private user-read-private"


# ==========================
# SPOTIFY AUTH SETUP
# ==========================
def create_spotify_oauth():
    cache_handler = FlaskSessionCacheHandler(session)
    return SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
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
    session.clear() 
    code = request.args.get("code")
    token_info = sp_oauth.get_access_token(code)
    return redirect("/")


# ==========================
# AUTH HELPERS
# ==========================
def get_sp_client():
    sp_oauth = create_spotify_oauth()
    if not sp_oauth.validate_token(sp_oauth.cache_handler.get_cached_token()):
        return None
    return spotipy.Spotify(oauth_manager=sp_oauth)

@auth_bp.route("/debug-token")
def debug_token():
    token_info = session.get("token_info")
    if not token_info:
        return jsonify({"status": "no token found in session"})
    
    return jsonify({
        "status": "authenticated",
        "active_scopes": token_info.get("scope", "unknown"),
        "expires_at": token_info.get("expires_at"),
        "is_expired": token_info.get("expires_at", 0) < datetime.now().timestamp()
    })

@auth_bp.route("/logout")
def logout():
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
        results = sp.current_user_top_tracks(limit=5, time_range='medium_term')
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
    user = sp.current_user()
    images = user.get("images", [])
    image_url = images[0]["url"] if images else None
    return jsonify({
        "display_name": user.get("display_name", "User"),
        "image": image_url
    })

@auth_bp.route("/get-collections")
def get_collections():
    sp = get_sp_client()
    if not sp: return jsonify({"error": "Not authenticated"}), 401

    try:
        user = sp.current_user()
        market = user.get("country")
        
        liked_total = 0
        try:
            liked_res = sp.current_user_saved_tracks(limit=1)
            liked_total = liked_res.get('total', 0)
        except: pass

        playlists_res = sp.current_user_playlists(limit=50)
        playlists = []
        
        for p in playlists_res.get('items', []):
            if not p: continue
            
            image_url = p.get('images')[0].get('url', "") if p.get('images') else ""
            owner_id = p.get('owner', {}).get('id')
            is_owner = owner_id == user.get('id')

            # Initial count from simplified object
            total_tracks = 0
            tracks_info = p.get('tracks', {})
            if isinstance(tracks_info, dict):
                total_tracks = tracks_info.get('total', 0)
            
            # SAFE FALLBACK: If 0, try a quick items check with market
            if total_tracks == 0:
                try:
                    # Use market to avoid 403s for region-restricted playlists
                    check = sp.playlist_items(p.get('id'), fields="total", limit=1, market=market)
                    if check and 'total' in check:
                        total_tracks = check['total']
                except:
                    pass

            playlists.append({
                "id": p.get('id'),
                "name": p.get('name'),
                "image": image_url,
                "total": total_tracks,
                "is_owner": is_owner
            })
            
        return jsonify({
            "liked_total": liked_total,
            "playlists": playlists
        })
    except Exception as e:
        logger.error(f"Collections fetch error: {e}")
        return jsonify({"error": str(e)}), 500

def clean_track_name(name: str) -> str:
    """Removes junk like (Remastered) or - Live from track names."""
    name = re.sub(r'\s*[\(\[].*?[\)\]]', '', name)
    name = re.sub(r'\s*-\s*(Remastered|Live|Radio Edit|Deluxe Edition|Single Version).*', '', name, flags=re.I)
    return name.strip()

@auth_bp.route("/fetch-collection-songs", methods=["POST"])
def fetch_collection_songs():
    sp = get_sp_client()
    if not sp: return jsonify({"error": "Not authenticated"}), 401

    data = request.json
    col_id = data.get("collection_id")
    col_name = data.get("collection_name")
    
    logger.info(f"FETCHING SONGS: Collection '{col_name}' (ID: {col_id})")
    logger.info(f"REDIRECT_URI_USED: {REDIRECT_URI}")

    try:
        if col_id == "liked":
            pl = sp.current_user_saved_tracks(limit=50)
        else:
            pl = sp.playlist_items(col_id, limit=50)
            
        if not pl:
            logger.error("Spotify API returned None for the collection.")
            return jsonify({"error": "spotify_error", "message": "Spotify returned no data."}), 500

        items = pl.get('items', [])
        logger.info(f"FETCH_DEBUG: Received {len(items)} items from Spotify.")
        
        if len(items) == 0:
            logger.warning(f"Collection '{col_name}' is literally empty according to Spotify.")
            return jsonify({
                "error": "empty_collection", 
                "message": f"Spotify says your '{col_name}' collection is empty. Make sure you are logged into the right account!"
            }), 400

        if len(items) > 0:
            # DEEP DUMP of the first item so we can see the exact structure in Vercel logs
            logger.info(f"RAW_ITEM_DUMP (FIRST): {str(items[0])[:1000]}...")

        raw_tracks = []
        for index, item in enumerate(items):
            if not item: continue
            
            # UNIVERSAL PARSER: Check all known nesting patterns
            track_obj = item.get('track') or item.get('item') or item.get('episode')
            
            # Fallback: Check if the item itself is the track
            if not track_obj or not isinstance(track_obj, dict):
                track_obj = item
            
            t_name = track_obj.get('name')
            t_artists = track_obj.get('artists', [])
            
            if t_name and isinstance(t_artists, list) and len(t_artists) > 0:
                raw_tracks.append(track_obj)
            else:
                logger.warning(f"Parser skipped item at index {index}: {t_name or 'No Name'}. Type: {track_obj.get('type', 'unknown')}")

        if not raw_tracks:
            logger.error(f"Failed to parse any valid tracks from {len(items)} items.")
            return jsonify({
                "error": "no_songs_found", 
                "message": f"Found {len(items)} items, but none matched the music structure. Check your Vercel logs for RAW_ITEM_DUMP."
            }), 400

        random.shuffle(raw_tracks)
        selected_tracks = raw_tracks[:10]

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
        return {"tags": tags, "playcount": playcount}
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
    final_data = [process_song_emotion(s) for s in enriched]
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "total_songs": len(final_data),
        "songs_with_lyrics": len([s for s in final_data if s.get("lyrics_found")]),
        "data": final_data
    })
