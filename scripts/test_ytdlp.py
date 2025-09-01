#!/usr/bin/env python3
import yt_dlp
import json

# Channel to test with - change this to any channel you want
channel_url = "https://www.youtube.com/@MrBeast"

print(f"Extracting info from: {channel_url}")

ydl_opts = {
    'quiet': True,
    'no_warnings': True,
    'playlistend': 10,  # Get last 10 videos
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Extract all channel info without downloading
        info = ydl.extract_info(channel_url, download=False)
        
        # Use sanitize_info to make it JSON serializable (official recommendation)
        sanitized_info = ydl.sanitize_info(info)
        
        # Save everything to JSON file
        with open('channel_info.json', 'w', encoding='utf-8') as f:
            json.dump(sanitized_info, f, indent=2, ensure_ascii=False)
        
        print("✅ Channel info saved to 'channel_info.json'")
        print(f"Channel: {info.get('title', 'Unknown')}")
        print(f"Videos found: {len(info.get('entries', []))}")
        
except Exception as e:
    print(f"❌ Error: {e}")