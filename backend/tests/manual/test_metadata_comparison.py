#!/usr/bin/env python3
"""
Test script to compare extract_channel_info() vs extract_channel_metadata_full()
from the YouTubeService class.

This script shows the differences between the two metadata extraction methods:
- extract_channel_info(): Fast, lightweight, basic channel info only
- extract_channel_metadata_full(): Comprehensive, saves JSON file, removes video entries

Usage:
    docker exec -it channelfinwatcher-backend-1 python /app/tests/manual/test_metadata_comparison.py
"""

import sys
import os
import json
import time
from pathlib import Path

# Add the app directory to Python path so we can import our modules
sys.path.insert(0, '/app')

from app.youtube_service import youtube_service
from app.config import get_settings

# Test channel - change this to any channel you want to test
TEST_CHANNEL_URL = "https://www.youtube.com/@MrBeast"

def format_file_size(size_bytes):
    """Convert bytes to human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_names[i]}"

def test_extract_channel_info():
    """Test the lightweight extract_channel_info method."""
    print("🔍 Testing extract_channel_info() [extract_flat: True]")
    print("-" * 60)
    
    start_time = time.time()
    success, channel_info, error = youtube_service.extract_channel_info(TEST_CHANNEL_URL)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    if success:
        print(f"✅ Success! Execution time: {execution_time:.2f} seconds")
        print(f"📊 Data returned: {len(str(channel_info))} characters")
        
        # Save to file for inspection
        output_file = "/app/tests/manual/basic_info.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(channel_info, f, indent=2, ensure_ascii=False)
        
        # Show key fields
        print("\n📋 Key fields available:")
        for key, value in channel_info.items():
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            print(f"  • {key}: {value}")
        
        return True, channel_info, execution_time, output_file
    else:
        print(f"❌ Failed: {error}")
        return False, None, execution_time, None

def test_extract_channel_metadata_full():
    """Test the comprehensive extract_channel_metadata_full method."""
    print("\n🔍 Testing extract_channel_metadata_full() [extract_flat: False]")
    print("-" * 60)
    
    # Create temporary output directory
    temp_dir = "/app/tests/manual/temp_metadata"
    os.makedirs(temp_dir, exist_ok=True)
    
    start_time = time.time()
    success, full_metadata, error = youtube_service.extract_channel_metadata_full(TEST_CHANNEL_URL, temp_dir)
    end_time = time.time()
    
    execution_time = end_time - start_time
    
    if success:
        print(f"✅ Success! Execution time: {execution_time:.2f} seconds")
        print(f"📊 Data returned: {len(str(full_metadata))} characters")
        
        # Find the generated JSON file
        json_files = list(Path(temp_dir).glob("*.info.json"))
        json_file_path = str(json_files[0]) if json_files else None
        
        if json_file_path:
            file_size = os.path.getsize(json_file_path)
            print(f"💾 JSON file created: {os.path.basename(json_file_path)}")
            print(f"📁 File size: {format_file_size(file_size)}")
        
        # Save full metadata to separate file for comparison
        comparison_file = "/app/tests/manual/full_metadata.json"
        with open(comparison_file, 'w', encoding='utf-8') as f:
            json.dump(full_metadata, f, indent=2, ensure_ascii=False)
        
        # Show key fields (limit output for readability)
        print("\n📋 Key fields available (sample):")
        field_count = 0
        for key, value in full_metadata.items():
            if field_count >= 15:  # Limit output since full metadata has many fields
                print(f"  ... and {len(full_metadata) - 15} more fields")
                break
            
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            elif isinstance(value, (list, dict)):
                value = f"<{type(value).__name__} with {len(value)} items>"
            
            print(f"  • {key}: {value}")
            field_count += 1
        
        return True, full_metadata, execution_time, json_file_path
    else:
        print(f"❌ Failed: {error}")
        return False, None, execution_time, None

def compare_results(basic_success, basic_data, basic_time, full_success, full_data, full_time):
    """Compare the results of both methods."""
    print("\n" + "="*80)
    print("🔄 COMPARISON RESULTS")
    print("="*80)
    
    if not basic_success or not full_success:
        print("⚠️  Cannot compare - one or both methods failed")
        return
    
    # Timing comparison
    print(f"\n⏱️  EXECUTION TIME:")
    print(f"   Basic method:  {basic_time:.2f}s")
    print(f"   Full method:   {full_time:.2f}s")
    print(f"   Difference:    {abs(full_time - basic_time):.2f}s ({full_time/basic_time:.1f}x slower)" if basic_time > 0 else "")
    
    # Data size comparison
    print(f"\n📊 DATA SIZE:")
    print(f"   Basic method:  {len(str(basic_data))} characters")
    print(f"   Full method:   {len(str(full_data))} characters")
    
    # Field comparison
    basic_fields = set(basic_data.keys()) if basic_data else set()
    full_fields = set(full_data.keys()) if full_data else set()
    
    print(f"\n📋 FIELD COMPARISON:")
    print(f"   Basic fields:     {len(basic_fields)}")
    print(f"   Full fields:      {len(full_fields)}")
    print(f"   Common fields:    {len(basic_fields & full_fields)}")
    print(f"   Only in basic:    {len(basic_fields - full_fields)}")
    print(f"   Only in full:     {len(full_fields - basic_fields)}")
    
    # Show unique fields
    only_basic = basic_fields - full_fields
    only_full = full_fields - basic_fields
    
    if only_basic:
        print(f"\n   🔹 Fields only in basic: {', '.join(sorted(only_basic))}")
    
    if only_full:
        full_unique_sample = sorted(only_full)[:10]  # Show first 10
        remaining = len(only_full) - 10
        print(f"   🔸 Fields only in full: {', '.join(full_unique_sample)}")
        if remaining > 0:
            print(f"      ... and {remaining} more")
    
    # Key data comparison
    print(f"\n🎯 KEY DATA COMPARISON:")
    common_fields = ['channel_id', 'name', 'title', 'description', 'subscriber_count', 'video_count']
    for field in common_fields:
        basic_val = basic_data.get(field, 'N/A') if basic_data else 'N/A'
        full_val = full_data.get(field, 'N/A') if full_data else 'N/A'
        
        if basic_val == full_val:
            print(f"   ✅ {field}: {basic_val}")
        else:
            print(f"   🔄 {field}:")
            print(f"      Basic: {basic_val}")
            print(f"      Full:  {full_val}")

def main():
    """Main test function."""
    print("🧪 YouTube Metadata Extraction Comparison Test")
    print("=" * 80)
    print(f"Testing channel: {TEST_CHANNEL_URL}")
    print("=" * 80)
    
    # Test basic method
    basic_success, basic_data, basic_time, basic_file = test_extract_channel_info()
    
    # Test full method
    full_success, full_data, full_time, full_file = test_extract_channel_metadata_full()
    
    # Compare results
    compare_results(basic_success, basic_data, basic_time, full_success, full_data, full_time)
    
    # Show output files
    print(f"\n📁 OUTPUT FILES:")
    if basic_file:
        print(f"   Basic info:      {basic_file}")
    if full_file:
        print(f"   Full metadata:   {full_file}")
        print(f"   Comparison:      /app/tests/manual/full_metadata.json")
    
    print(f"\n💡 TIP: You can inspect the JSON files to see detailed differences:")
    print(f"   docker exec -it channelfinwatcher-backend-1 cat /app/tests/manual/basic_info.json")
    print(f"   docker exec -it channelfinwatcher-backend-1 cat /app/tests/manual/full_metadata.json")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()