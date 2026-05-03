# app/services/processing.py

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

        try:
            lyrics_data = self.api.get_lyrics(
                track_name=track_name,
                artist_name=artist_name,
                album_name=album_name,
                duration=duration
            )

            if not lyrics_data:
                logger.info(f"     ℹ️  Retrying without album name for: {track_name} — {artist_name}")
                lyrics_data = self.api.get_lyrics(
                    track_name=track_name,
                    artist_name=artist_name
                )

            if lyrics_data:
                return {
                    "plain_lyrics": lyrics_data.plain_lyrics,
                    "synced_lyrics": lyrics_data.synced_lyrics
                }
            return None

        except Exception as e:
            logger.warning(f"Lyrics fetch failed: {track_name} - {artist_name} | {e}")
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
            # "synced_lyrics": None,
            "lyrics_found": False
        }

    # First attempt with album_name
    lyrics_data = fetcher.get_lyrics(
        track_name=track,
        artist_name=artist,
        album_name=album
    )

    # If not found with album_name, retry without it
    if not lyrics_data:
        logger.info(f"     ℹ️  Retrying without album name for: {track} — {artist}")
        lyrics_data = fetcher.get_lyrics(
            track_name=track,
            artist_name=artist
        )

    # Normalize result and decide whether lyrics were found
    plain = None
    synced = None
    found = False
    if lyrics_data:
        plain = lyrics_data.get("plain_lyrics") if isinstance(lyrics_data, dict) else None
        # synced = lyrics_data.get("synced_lyrics") if isinstance(lyrics_data, dict) else None
        found = bool(plain or synced)

    return {
        **song,
        "plain_lyrics": plain,
        # "synced_lyrics": synced,
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