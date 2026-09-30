"""
Unit tests for the media library layout (app/media_layout.py).

The layout decides how Jellyfin (and Infuse, through Jellyfin) orders episodes,
so these tests pin down the filename yt-dlp produces and check that the NFO
season/episode numbers always agree with it.
"""

import os
import xml.etree.ElementTree as ET

import pytest
import yt_dlp

from app.media_layout import (
    OUTPUT_TEMPLATE,
    episode_numbers,
    parse_season_dir,
    season_dir_name,
)
from app.nfo_service import NFOService

# 2021-12-07 15:30:00 UTC
TIMESTAMP = 1638891000

BASE_INFO = {
    'channel': 'Ms Rachel',
    'channel_id': 'UCabc',
    'title': 'Learn Colors',
    'id': 'abcdefghijk',
    'ext': 'mkv',
    'upload_date': '20211207',
}


def _render(info):
    return yt_dlp.YoutubeDL({'quiet': True}).prepare_filename(info, outtmpl=OUTPUT_TEMPLATE)


class TestOutputTemplate:
    def test_uses_season_folder_and_episode_code(self):
        path = _render({**BASE_INFO, 'timestamp': TIMESTAMP})
        episode = 'S2021E12071530 - Learn Colors [abcdefghijk]'
        assert path == f'Ms Rachel [UCabc]/Season 2021/{episode}/{episode}.mkv'

    def test_falls_back_to_date_without_timestamp(self):
        path = _render(BASE_INFO)
        assert os.path.basename(path) == 'S2021E12070000 - Learn Colors [abcdefghijk].mkv'

    @pytest.mark.parametrize('timestamp', [TIMESTAMP, None])
    def test_filename_matches_episode_numbers(self, timestamp):
        """The SxxxxEyyyy in the filename and the NFO numbers must agree."""
        info = {**BASE_INFO, 'timestamp': timestamp}
        if timestamp is None:
            del info['timestamp']
        season, episode = episode_numbers(info)
        assert os.path.basename(_render(info)).startswith(f'S{season}E{episode:08d} ')

    def test_same_day_uploads_sort_in_upload_order(self):
        morning = episode_numbers({**BASE_INFO, 'timestamp': TIMESTAMP - 6 * 3600})
        afternoon = episode_numbers({**BASE_INFO, 'timestamp': TIMESTAMP})
        assert morning < afternoon


class TestEpisodeNumbers:
    def test_with_timestamp(self):
        assert episode_numbers({'upload_date': '20211207', 'timestamp': TIMESTAMP}) == (2021, 12071530)

    def test_without_timestamp(self):
        assert episode_numbers({'upload_date': '20210105'}) == (2021, 1050000)

    @pytest.mark.parametrize('upload_date', [None, '', 'NA', '2021-12-07'])
    def test_missing_or_bad_upload_date(self, upload_date):
        assert episode_numbers({'upload_date': upload_date, 'timestamp': TIMESTAMP}) is None


class TestSeasonDirs:
    @pytest.mark.parametrize('name,expected', [
        ('Season 2021', 2021),
        ('2021', 2021),        # legacy layout
        ('Season 1', None),
        ('Specials', None),
        ('20211', None),
    ])
    def test_parse_season_dir(self, name, expected):
        assert parse_season_dir(name) == expected

    def test_season_dir_name(self):
        assert season_dir_name(2021) == 'Season 2021'


class TestNfoUsesLayout:
    def test_episode_nfo_has_season_episode_and_stable_dateadded(self, tmp_path):
        video = tmp_path / 'S2021E12071530 - Learn Colors [abcdefghijk].mkv'
        video.touch()
        os.utime(video, (TIMESTAMP, TIMESTAMP))
        (tmp_path / 'S2021E12071530 - Learn Colors [abcdefghijk].info.json').write_text(
            '{"title": "Learn Colors", "channel": "Ms Rachel", "id": "abcdefghijk",'
            ' "upload_date": "20211207", "timestamp": %d}' % TIMESTAMP
        )

        success, error = NFOService(str(tmp_path)).generate_episode_nfo(str(video), None)

        assert success, error
        root = ET.parse(tmp_path / 'S2021E12071530 - Learn Colors [abcdefghijk].nfo').getroot()
        assert root.find('season').text == '2021'
        assert root.find('episode').text == '12071530'
        # dateadded comes from the video file, so regenerating doesn't change it
        from datetime import datetime
        assert root.find('dateadded').text == datetime.fromtimestamp(TIMESTAMP).strftime('%Y-%m-%d %H:%M:%S')

    def test_episode_nfo_without_upload_date_has_no_numbers(self, tmp_path):
        video = tmp_path / 'video [abcdefghijk].mkv'
        video.touch()
        (tmp_path / 'video [abcdefghijk].info.json').write_text('{"title": "T", "channel": "C"}')

        success, _ = NFOService(str(tmp_path)).generate_episode_nfo(str(video), None)

        assert success
        root = ET.parse(tmp_path / 'video [abcdefghijk].nfo').getroot()
        assert root.find('season') is None
        assert root.find('episode') is None

    def test_season_nfo_accepts_season_folder(self, tmp_path):
        season_dir = tmp_path / 'Season 2021'
        season_dir.mkdir()

        success, error = NFOService(str(tmp_path)).generate_season_nfo(str(season_dir))

        assert success, error
        root = ET.parse(season_dir / 'season.nfo').getroot()
        assert root.find('seasonnumber').text == '2021'
        assert root.find('title').text == '2021'
