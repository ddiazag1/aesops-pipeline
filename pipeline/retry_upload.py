#!/usr/bin/env python3
"""
YouTube Retry Uploader for Aesop's Storyhouse
Handles OAuth2 auth and video uploads via YouTube Data API.

In CI mode, credentials are restored from environment variables (base64-encoded).
"""

import os
import sys
import json
import pickle
import base64
import time
from pathlib import Path
from typing import Optional, List, Dict

# Fix Windows Unicode
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def sanitize_tags(tags, max_tags=15, max_total_chars=400):
    """Clean tags to pass YouTube validation."""
    import re as _re
    clean = []
    total_chars = 0
    for tag in tags:
        tag = _re.sub(r'[<>"\']', '', str(tag))
        tag = _re.sub(r'[^\w\s\-&]', '', tag)
        tag = tag.strip()
        if not tag or len(tag) < 2 or len(tag) > 30:
            continue
        if len(clean) >= max_tags:
            break
        if total_chars + len(tag) > max_total_chars:
            break
        clean.append(tag)
        total_chars += len(tag)
    return clean


# ===================================================================
# CONFIG
# ===================================================================

CI_MODE = os.getenv('CI', '').lower() == 'true' or os.getenv('GITHUB_ACTIONS', '').lower() == 'true'

# In CI, credential files are in the pipeline/ directory
PIPELINE_DIR = Path(__file__).parent
YOUTUBE_TOKEN_FILE = str(PIPELINE_DIR / "youtube_token.pickle")
YOUTUBE_CREDENTIALS_FILE = str(PIPELINE_DIR / "youtube_credentials.json")

YOUTUBE_SCOPES = [
    'https://www.googleapis.com/auth/youtube.force-ssl',
    'https://www.googleapis.com/auth/youtube.upload',
]
YOUTUBE_CHANNEL = "https://www.youtube.com/@AesopsStoryhouse"

# Playlist mapping
PLAYLIST_MAP = {
    "color":    {"en": "Learn Colors | Aesop's Storyhouse",
                 "es": "Aprende los Colores | Aesop's Storyhouse"},
    "number":   {"en": "Counting & Numbers | Aesop's Storyhouse",
                 "es": "Contar y Numeros | Aesop's Storyhouse"},
    "shape":    {"en": "Shapes for Kids | Aesop's Storyhouse",
                 "es": "Figuras para Ninos | Aesop's Storyhouse"},
    "animal":   {"en": "Animal Adventures | Aesop's Storyhouse",
                 "es": "Aventuras con Animales | Aesop's Storyhouse"},
    "opposite": {"en": "Opposites & Concepts | Aesop's Storyhouse",
                 "es": "Opuestos y Conceptos | Aesop's Storyhouse"},
    "size":     {"en": "Opposites & Concepts | Aesop's Storyhouse",
                 "es": "Opuestos y Conceptos | Aesop's Storyhouse"},
}

_playlist_id_cache = {}


# ===================================================================
# RESTORE CREDENTIALS FROM ENV (CI MODE)
# ===================================================================

def restore_credentials_from_env():
    """In CI, restore YouTube credentials from base64-encoded secrets."""
    creds_b64 = os.getenv('YOUTUBE_CREDENTIALS_JSON')
    token_b64 = os.getenv('YOUTUBE_TOKEN_PICKLE')

    if creds_b64:
        creds_data = base64.b64decode(creds_b64)
        with open(YOUTUBE_CREDENTIALS_FILE, 'wb') as f:
            f.write(creds_data)
        print("  [OK] Restored youtube_credentials.json from env")

    if token_b64:
        token_data = base64.b64decode(token_b64)
        with open(YOUTUBE_TOKEN_FILE, 'wb') as f:
            f.write(token_data)
        print("  [OK] Restored youtube_token.pickle from env")


# ===================================================================
# YOUTUBE AUTH
# ===================================================================

def get_youtube_service():
    """Authenticate and return YouTube API service."""
    if CI_MODE:
        restore_credentials_from_env()

    creds = None
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        with open(YOUTUBE_TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed token
            with open(YOUTUBE_TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
            print("  [OK] Refreshed YouTube token")
        elif not CI_MODE:
            # Only run interactive flow locally
            flow = InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_CREDENTIALS_FILE, YOUTUBE_SCOPES)
            creds = flow.run_local_server(port=0)
            with open(YOUTUBE_TOKEN_FILE, 'wb') as token:
                pickle.dump(creds, token)
        else:
            print("  [ERROR] YouTube token expired and cannot refresh in CI")
            return None

    return build('youtube', 'v3', credentials=creds)


def get_updated_token_b64():
    """Return the current token as base64 (for updating the GitHub secret)."""
    if os.path.exists(YOUTUBE_TOKEN_FILE):
        with open(YOUTUBE_TOKEN_FILE, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    return None


# ===================================================================
# UPLOAD
# ===================================================================

def upload_to_youtube(youtube, video_path, title, description, is_short=False, thumbnail_path=None, tags=None):
    """Upload a single video to YouTube."""
    if not video_path.exists():
        print(f"   [ERROR] File not found: {video_path}")
        return None

    if is_short and '#Shorts' not in title:
        title = f"{title} #Shorts"

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": sanitize_tags(tags or []),
            "categoryId": "22",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,
        }
    }

    media = MediaFileUpload(str(video_path), chunksize=10485760, resumable=True)

    try:
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   {int(status.progress() * 100)}%", end='\r', flush=True)

        video_id = response['id']
        url = f"https://www.youtube.com/watch?v={video_id}"
        print(f"   [OK] {title[:50]} -> {url}")

        # Set thumbnail
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path))
                ).execute()
                print(f"   [OK] Thumbnail set")
            except Exception as e:
                print(f"   [WARN] Thumbnail failed: {e}")

        return url

    except Exception as e:
        print(f"   [ERROR] Upload failed: {e}")
        return None


# ===================================================================
# PLAYLIST
# ===================================================================

def find_playlist(youtube, playlist_title):
    """Find an existing playlist by title."""
    global _playlist_id_cache
    if playlist_title in _playlist_id_cache:
        return _playlist_id_cache[playlist_title]

    try:
        next_page = None
        while True:
            response = youtube.playlists().list(
                part="id,snippet", mine=True, maxResults=50, pageToken=next_page,
            ).execute()
            for item in response.get('items', []):
                _playlist_id_cache[item['snippet']['title']] = item['id']
            next_page = response.get('nextPageToken')
            if not next_page:
                break
    except Exception:
        pass

    return _playlist_id_cache.get(playlist_title)


def add_to_playlist(youtube, playlist_id, video_url):
    """Add video to playlist by URL."""
    if not playlist_id or not video_url:
        return False

    video_id = None
    if 'watch?v=' in video_url:
        video_id = video_url.split('watch?v=')[-1].split('&')[0]
    if not video_id:
        return False

    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={
                "snippet": {
                    "playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id},
                }
            }
        ).execute()
        return True
    except Exception:
        return False


# ===================================================================
# CLI
# ===================================================================

def find_video_folder(path_arg):
    """Resolve 'latest' or a folder path."""
    if path_arg.lower() == "latest":
        videos_dir = Path("videos")
        if not videos_dir.exists():
            print("[ERROR] 'videos' folder not found")
            sys.exit(1)
        folders = sorted([f for f in videos_dir.iterdir() if f.is_dir()],
                         key=lambda f: f.stat().st_mtime, reverse=True)
        if not folders:
            print("[ERROR] No video folders found")
            sys.exit(1)
        return folders[0]
    else:
        p = Path(path_arg)
        if not p.exists():
            p = Path("videos") / path_arg
        if not p.exists():
            print(f"[ERROR] Folder not found: {path_arg}")
            sys.exit(1)
        return p


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("   python retry_upload.py latest")
        print("   python retry_upload.py <folder_name>")
        sys.exit(1)

    folder = find_video_folder(sys.argv[1])
    print(f"[OK] Using folder: {folder.name}")

    # Load metadata
    seo_path = folder / "seo_metadata.json"
    content_path = folder / "content.json"

    if not seo_path.exists():
        print("[ERROR] seo_metadata.json not found")
        sys.exit(1)

    with open(seo_path, 'r', encoding='utf-8') as f:
        seo_data = json.load(f)
    with open(content_path, 'r', encoding='utf-8') as f:
        content = json.load(f)

    seo_en = seo_data.get('metadata_en', {})
    title = seo_en.get('youtube_titles', [content.get('title', 'Video')])[0]
    tags = seo_en.get('youtube_tags', [])
    description = seo_en.get('youtube_description', '')

    youtube = get_youtube_service()

    # Find and upload main video
    main_video = folder / "final_bilingual.mp4"
    if main_video.exists():
        upload_to_youtube(youtube, main_video, title, description, tags=tags)

    # Find and upload shorts
    shorts_folder = folder / "shorts"
    if shorts_folder.exists():
        shorts_titles = seo_en.get('youtube_shorts_titles', {})
        for kid in ['liam', 'noah', 'oliver', 'emma']:
            short_path = shorts_folder / f"short_{kid}_bilingual.mp4"
            if short_path.exists():
                short_title = shorts_titles.get(kid.capitalize(), f"{kid.capitalize()} Learns!")
                upload_to_youtube(youtube, short_path, short_title, description,
                                  is_short=True, tags=tags)
