import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8000/callback")

# Same scopes as the main app
SCOPE = "user-top-read playlist-read-private playlist-read-collaborative user-library-read"

def run_test():
    print("=== SPOTIFY FETCH TEST ===")
    
    if not CLIENT_ID or not CLIENT_SECRET:
        print("ERROR: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not found in .env")
        return

    sp_oauth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        open_browser=True # This will attempt to open your browser
    )

    print("Authenticating...")
    sp = spotipy.Spotify(auth_manager=sp_oauth)

    try:
        user = sp.current_user()
        print(f"Logged in as: {user['display_name']} ({user['id']})")
        print("-" * 30)

        # 1. Test Liked Songs
        print("Fetching Liked Songs...")
        liked = sp.current_user_saved_tracks(limit=1)
        print(f"✅ Liked Songs Total: {liked.get('total')} tracks")
        print("-" * 30)

        # 2. Test Playlists
        print("Fetching Playlists...")
        playlists = sp.current_user_playlists(limit=50)
        print(f"Found {len(playlists['items'])} playlists.")
        print("-" * 30)

        for i, p in enumerate(playlists['items']):
            name = p.get('name')
            p_id = p.get('id')
            
            # Check the tracks field structure
            tracks_data = p.get('tracks')
            
            print(f"Playlist #{i+1}: {name}")
            print(f"  ID: {p_id}")
            print(f"  Tracks Field Type: {type(tracks_data)}")
            
            if isinstance(tracks_data, dict):
                total = tracks_data.get('total')
                print(f"  Total (from dict): {total}")
            else:
                print(f"  Tracks Data: {tracks_data}")
            
            # Try fetching tracks directly for this playlist as a cross-check
            try:
                real_tracks = sp.playlist_tracks(p_id, fields="total", limit=1)
                print(f"  ✅ Verified Total (via API call): {real_tracks.get('total')}")
            except Exception as e:
                print(f"  ❌ Failed to verify tracks: {e}")
            
            print("-" * 30)

    except Exception as e:
        print(f"FATAL ERROR during fetch: {e}")

if __name__ == "__main__":
    run_test()
