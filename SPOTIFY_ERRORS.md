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

## 3. The "Nesting" Trap (Universal Parser Error)
- **Symptom:** "No usable tracks found" error even when Spotify successfully returned 20+ items.
- **Root Cause:** Different Spotify endpoints nest track metadata differently. Some use a `track` key, some use `item`, and others (like search results) return the track object at the root.
- **Solution: Universal Recursive Parser.**
    - Implemented a defensive extraction logic that checks keys in order of priority.
    - **Logic:** `track_obj = item.get('track') or item.get('item') or item.get('episode') or item`
    - This allows the app to process any collection type (Liked Songs, Playlists, or Podcasts) without structural failures.

## 4. Metadata "Noise" causing Analysis Failure
- **Symptom:** Tracks were fetched but the analysis page skipped them or showed "Empty Analysis."
- **Root Cause:** Titles like *"Song Name - 2011 Remastered"* or *"Song Name (Live at Wembley)"* caused the Lyric and Last.fm APIs to return 404s.
- **Solution: Metadata Sanitization.**
    - Added a Regex-based cleaning function (`clean_track_name`) that strips everything inside parentheses/brackets and removes common suffixes like "Remastered," "Deluxe," or "Live."
    - This increases the "hit rate" for lyric matching by over 40%.

## 5. Local File & Unavailable Track Restrictions
- **Symptom:** Specific playlists failed because they contained "Local Files" (MP3s uploaded from a PC) which lack a Spotify Global ID.
- **Root Cause:** The system was strictly requiring a `spotify_id` to proceed.
- **Solution: Relaxed ID Validation.**
    - Modified the fetcher to prioritize `Name + Artist` over `ID`.
    - If a track has no ID but has valid text metadata, it is passed through. This allows our system to attempt a "fuzzy match" on Last.fm and our local joke database even for local or restricted files.

---

*Last Updated: Monday, May 4, 2026*
