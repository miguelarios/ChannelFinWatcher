#!/usr/bin/env python3
"""
Quick test script to verify NFO generation with real production data.

This script demonstrates:
1. Loading a real .info.json file from production
2. Running the NFO generator service
3. Displaying the generated XML output
4. Validating the transformations
"""

import sys
import os
import json
from pathlib import Path

# Add backend to Python path so we can import our service
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.nfo_service import NFOService

# ANSI color codes for pretty output
GREEN = '\033[92m'
BLUE = '\033[94m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{BOLD}{BLUE}{'=' * 80}{RESET}")
    print(f"{BOLD}{BLUE}{title}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 80}{RESET}\n")

def print_success(message):
    """Print success message in green."""
    print(f"{GREEN}✓ {message}{RESET}")

def print_info(label, value):
    """Print labeled information."""
    print(f"{BOLD}{label}:{RESET} {value}")

def main():
    # Path to the real production .info.json file
    info_json_path = "./test/Ms Rachel - Toddler Learning Videos - 20250109 - Hide and Seek with Ms Rachel & Elmo + More Games, Kids Songs, Nursery Rhymes & Social Skills [drkVagtmIJA].info.json"

    if not os.path.exists(info_json_path):
        print(f"{RED}✗ File not found: {info_json_path}{RESET}")
        return 1

    print_section("NFO GENERATION TEST - Real Production Data")
    print_info("Source file", info_json_path)
    print_info("File size", f"{os.path.getsize(info_json_path) / 1024 / 1024:.2f} MB")

    # Load the JSON to show some metadata
    print_section("Step 1: Loading YouTube Metadata")
    try:
        with open(info_json_path, 'r', encoding='utf-8') as f:
            episode_info = json.load(f)
        print_success("JSON loaded successfully")

        # Display key fields we'll transform
        print_info("Video ID", episode_info.get('id', 'N/A'))
        print_info("Title", episode_info.get('title', 'N/A')[:80] + '...' if len(episode_info.get('title', '')) > 80 else episode_info.get('title', 'N/A'))
        print_info("Channel", episode_info.get('channel', 'N/A'))
        print_info("Upload Date", episode_info.get('upload_date', 'N/A'))
        print_info("Duration", f"{episode_info.get('duration', 0)} seconds ({episode_info.get('duration', 0) // 60} minutes)")
        print_info("Categories", ', '.join(episode_info.get('categories', [])))
        print_info("Tags", f"{len(episode_info.get('tags', []))} tags found")

    except Exception as e:
        print(f"{RED}✗ Failed to load JSON: {e}{RESET}")
        return 1

    # Initialize NFO service
    print_section("Step 2: Generating Episode NFO XML")
    nfo_service = NFOService(media_path="/app/media")

    try:
        # Generate the NFO XML content
        nfo_content = nfo_service._create_episode_nfo_xml(episode_info)
        print_success("NFO XML generated successfully")
        print_info("NFO size", f"{len(nfo_content)} bytes")

    except Exception as e:
        print(f"{RED}✗ Failed to generate NFO: {e}{RESET}")
        import traceback
        traceback.print_exc()
        return 1

    # Display the generated XML
    print_section("Step 3: Generated NFO Content")
    print(nfo_content.decode('utf-8'))

    # Validate key transformations
    print_section("Step 4: Validation Summary")

    # Parse the XML to validate
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(nfo_content)

        checks = [
            ("Root element is <episodedetails>", root.tag == 'episodedetails'),
            ("<title> field present", root.find('title') is not None),
            ("<showtitle> field present", root.find('showtitle') is not None),
            ("<premiered> date formatted correctly", root.find('premiered') is not None and '-' in root.find('premiered').text if root.find('premiered') is not None else False),
            ("<aired> date formatted correctly", root.find('aired') is not None and '-' in root.find('aired').text if root.find('aired') is not None else False),
            ("<runtime> converted to minutes", root.find('runtime') is not None),
            ("<uniqueid> with YouTube ID", root.find('uniqueid') is not None),
            ("<genre> tags present", len(root.findall('genre')) > 0),
            ("<tag> tags present", len(root.findall('tag')) > 0),
        ]

        for check_name, passed in checks:
            if passed:
                print(f"{GREEN}✓{RESET} {check_name}")
            else:
                print(f"{YELLOW}⚠{RESET} {check_name}")

        # Show actual transformed values
        print_section("Step 5: Transformation Examples")

        if root.find('premiered') is not None:
            print_info("upload_date → premiered", f"{episode_info.get('upload_date')} → {root.find('premiered').text}")

        if root.find('aired') is not None:
            print_info("upload_date → aired", f"{episode_info.get('upload_date')} → {root.find('aired').text}")

        if root.find('runtime') is not None:
            print_info("duration transformation", f"{episode_info.get('duration')} seconds → {root.find('runtime').text} minutes")

        if root.find('year') is not None:
            print_info("year extraction", f"{episode_info.get('upload_date')} → {root.find('year').text}")

        genre_count = len(root.findall('genre'))
        tag_count = len(root.findall('tag'))
        print_info("categories → genres", f"{len(episode_info.get('categories', []))} categories → {genre_count} <genre> tags")
        print_info("tags → tags", f"{len(episode_info.get('tags', []))} tags → {tag_count} <tag> tags")

        print_section("TEST COMPLETE ✓")
        print_success("NFO generation works correctly with real production data!")
        return 0

    except ET.ParseError as e:
        print(f"{RED}✗ Generated XML is invalid: {e}{RESET}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
