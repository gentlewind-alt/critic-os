# app/services/processing.py

from services.cache import cache_get, cache_set
from lrclib import LrcLibAPI
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


# ==========================
# LYRIC FETCHER (CORE CLASS)
# ==========================
class LyricFetcher:
    def __init__(self, user_agent: str = "critic-os/1.0.0"):
        self.api = LrcLibAPI(user_agent=user_agent)

    def get_lyrics(
        self,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[int] = None
    ) -> Optional[Dict]:
        """
        Attempts to get lyrics using multiple strategies:
        1. Exact match (get_lyrics)
        2. Fuzzy search (search_lyrics)
        """
        # Check Redis cache first
        cache_key = f"lyrics:{artist_name}:{track_name}".lower()
        cached = cache_get(cache_key)
        if cached:
            logger.info(f"     ✅ Found lyrics in Redis cache: {track_name}")
            return cached

        lyrics_data = None

        # STRATEGY 1: Exact Match
        try:
            lyrics_data = self.api.get_lyrics(
                track_name=track_name,
                artist_name=artist_name,
                album_name=album_name,
                duration=duration
            )
        except Exception as e:
            # LrcLibAPI often raises 404 if exact match fails
            logger.info(f"     ℹ️ Exact match failed (Strategy 1): {e}")

        # STRATEGY 2: Fuzzy Search
        if not lyrics_data:
            try:
                logger.info(f"     🔍 Attempting search (Strategy 2): {track_name} — {artist_name}")
                # We use a combined query string for the best fuzzy results
                query = f"{track_name} {artist_name}"
                search_results = self.api.search_lyrics(query=query)
                
                if search_results and len(search_results) > 0:
                    # Pick the first result that has plain lyrics
                    for res in search_results:
                        if res.plain_lyrics:
                            lyrics_data = res
                            logger.info(f"     ✅ Found match via search: {res.track_name} by {res.artist_name}")
                            break
            except Exception as e:
                logger.warning(f"     ❌ Search failed (Strategy 2): {e}")

        if lyrics_data:
            result = {
                "plain_lyrics": lyrics_data.plain_lyrics,
                "synced_lyrics": getattr(lyrics_data, 'synced_lyrics', None)
            }
            # Cache the result for 7 days
            cache_set(cache_key, result, ex=604800)
            return result
        
        return None


# ==========================
# SINGLE SONG PROCESSING
# ==========================
def process_song(song: Dict, fetcher: LyricFetcher) -> Dict:
    """
    Enrich a single song with lyrics
    """

    track = song.get("track_name")
    artist = song.get("artist_name")
    album = song.get("album_name")

    # If the input is missing required metadata, skip fetching
    if not track or not artist:
        logger.warning(f"Missing track or artist for song: {song}")
        return {
            **song,
            "plain_lyrics": None,
            "lyrics_found": False
        }

    # Use the improved multi-strategy fetcher
    lyrics_data = fetcher.get_lyrics(
        track_name=track,
        artist_name=artist,
        album_name=album
    )

    plain = None
    found = False
    if lyrics_data:
        plain = lyrics_data.get("plain_lyrics")
        found = bool(plain)

    return {
        **song,
        "plain_lyrics": plain,
        "lyrics_found": found
    }


# ==========================
# OPTIONAL: NON-STREAM MODE
# ==========================
def process_songs_batch(songs: List[Dict]) -> List[Dict]:
    """
    If you need full result (non-stream)
    """ 

    fetcher = LyricFetcher()
    results = []

    for song in songs:
        results.append(process_song(song, fetcher))

    return results