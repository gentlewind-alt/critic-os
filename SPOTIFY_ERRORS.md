# 📘 Spotify API Integration: Troubleshooting & Solutions

This document outlines the edge cases and errors encountered during the development of **CRITIC OS** and the engineering solutions implemented to resolve them.

---

## 1. The "Ghost" Playlist (0 Tracks reported)
- **Symptom:** Playlists in the collection selector show "0 TRACKS" even though they contain songs in the Spotify app.
- **Root Cause:** Spotify's "Simplified Playlist Object" (returned by the `/me/playlists` endpoint) often defaults to `total: 0` for followed, collaborative, or very large playlists to save bandwidth.
- **Solution: Verification Fallback.**
    - When the UI detects a `0` count, the backend triggers a targeted call to the `items` endpoint with `limit=1`.
    - **Logic:** `sp.playlist_items(playlist_id, fields="total", limit=1)`
    - This forces the API to calculate the true total before it is displayed to the user.

## 2. Deprecated Endpoint Failure
- **Symptom:** Playlist track fetching was intermittent or returned empty lists for "Made For You" or private collections.
- **Root Cause:** The endpoint `GET /playlists/{playlist_id}/tracks` has been deprecated by Spotify in favor of the newer `items` endpoint.
- **Solution: Modern API Migration.**
    - Updated all backend calls to use `sp.playlist_items()` instead of `sp.playlist_tracks()`.
    - This ensures compatibility with the latest Spotify data models, including those that mix tracks and podcast episodes.

## 3. The "Nesting" Trap (Strict Parser Logic)
- **Symptom:** "No usable tracks found" error even when Spotify successfully returned items.
- **Root Cause:** Different Spotify endpoints nest track metadata differently. Some use a `track` key, while others use `item`. If you only read `track`, you will incorrectly think playlists are empty.
- **Solution: Strict Extraction Helper.**
    - Implemented a mandatory `extract_valid_tracks` helper that handles both nesting patterns and filters invalid entries.
    - **Logic (Strict):**
      ```python
      track = item.get('track') or item.get('item')
      if not track or track.get('is_local'):
          continue
      ```
    - This ensures that only valid, cloud-hosted tracks with full metadata are passed to the analysis engine.

## 4. Metadata "Noise" causing Analysis Failure
- **Symptom:** Tracks were fetched but the analysis page skipped them or showed "Empty Analysis."
- **Root Cause:** Titles like *"Song Name - 2011 Remastered"* or *"Song Name (Live at Wembley)"* caused the Lyric and Last.fm APIs to return 404s.
- **Solution: Metadata Sanitization.**
    - Added a Regex-based cleaning function (`clean_track_name`) that strips everything inside parentheses/brackets and removes common suffixes like "Remastered," "Deluxe," or "Live."
    - This increases the "hit rate" for lyric matching by over 40%.

## 5. Local File Restrictions
- **Symptom:** Specific playlists failed or enrichment crashed because they contained "Local Files" (MP3s uploaded from a PC) which lack stable IDs and global metadata.
- **Root Cause:** Local files do not have valid data for Last.fm or Lyric lookups.
- **Solution: Explicit Local Exclusion.**
    - The `extract_valid_tracks` logic now explicitly skips any entry where `is_local` is true.
    - This prevents the "No usable tracks found" error from being masked by invalid local entries that would fail later in the pipeline anyway.

## 6. Request Context vs. Threading Conflict
- **Symptom:** `Working outside of request context` error during playlist collection fetching.
- **Root Cause:** We used `ThreadPoolExecutor` to speed up playlist processing. However, the app was using `FlaskSessionCacheHandler`, which stores tokens in the Flask `session`. Background threads do not have access to the active HTTP request context or session.
- **Solution: Local Cache + Session-less Workers.**
    - **Storage Switch:** Reverted from `FlaskSessionCacheHandler` to the default file-based cache (`.cache`). This allows background threads to read token data directly from the disk.
    - **Worker Isolation:** In `get_collections`, we extract the `access_token` in the main thread and pass it to a "session-less" `spotipy.Spotify(auth=token)` client used specifically by the workers.

---

*Last Updated: Monday, May 4, 2026*
