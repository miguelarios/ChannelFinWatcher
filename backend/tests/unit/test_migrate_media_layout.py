"""
Unit tests for the media layout migration CLI (app/migrate_media_layout.py).

These build a channel folder in the legacy layout on disk, then check:
- the dry run reports the plan and changes nothing
- --apply moves every sidecar file, regenerates NFOs, updates the database
- running it again is a no-op, and existing files are never overwritten
- leftover files that belong to no video are listed, and moved aside only
  with --remove-leftovers
"""

import json
import os
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yt_dlp

from app.migrate_media_layout import apply_plan, plan_channel, run
from app.models import Channel, Download
from app.nfo_service import NFOService

# 2021-12-07 15:30:00 UTC
TIMESTAMP = 1638891000
NEW_EPISODE = 'S2021E12071530 - Learn Colors [abcdefghijk]'


def _legacy_video(channel_dir, video_id='abcdefghijk', title='Learn Colors',
                  upload_date='20211207', timestamp=TIMESTAMP, info=True):
    """Create a video in the old layout; return its path."""
    year = upload_date[:4]
    stem = f'Ms Rachel - {upload_date} - {title} [{video_id}]'
    video_dir = os.path.join(channel_dir, year, stem)
    os.makedirs(video_dir, exist_ok=True)
    video = os.path.join(video_dir, stem + '.mkv')
    open(video, 'w').close()
    for suffix in ('.nfo', '.webp', '.en.vtt'):
        open(os.path.join(video_dir, stem + suffix), 'w').close()
    if info:
        with open(os.path.join(video_dir, stem + '.info.json'), 'w') as f:
            json.dump({'id': video_id, 'title': title, 'channel': 'Ms Rachel',
                       'channel_id': 'UCabc', 'upload_date': upload_date,
                       'timestamp': timestamp, 'ext': 'webm'}, f)
    with open(os.path.join(channel_dir, year, 'season.nfo'), 'w') as f:
        f.write('<season/>')
    return video


def _orphan_info(channel_dir, video_id='zzzzzzzzzzz', upload_date='20210301'):
    """Create a lone .info.json in the old layout (a failed download's remains)."""
    stem = f'Ms Rachel - {upload_date} - Gone [{video_id}]'
    video_dir = os.path.join(channel_dir, upload_date[:4], stem)
    os.makedirs(video_dir, exist_ok=True)
    path = os.path.join(video_dir, stem + '.info.json')
    with open(path, 'w') as f:
        json.dump({'id': video_id, 'upload_date': upload_date}, f)
    return path


@pytest.fixture
def channel_dir(tmp_path):
    path = tmp_path / 'Ms Rachel [UCabc]'
    path.mkdir()
    return str(path)


@pytest.fixture
def ydl():
    return yt_dlp.YoutubeDL({'quiet': True})


class TestPlanChannel:
    def test_plans_rename_for_legacy_video(self, channel_dir, ydl):
        _legacy_video(channel_dir)

        plan = plan_channel(channel_dir, ydl)

        assert len(plan.moves) == 1
        move = plan.moves[0]
        assert move.new_video_path == os.path.join(
            channel_dir, 'Season 2021', NEW_EPISODE, NEW_EPISODE + '.mkv')
        assert sorted(os.path.basename(dst) for _src, dst in move.file_moves) == sorted(
            NEW_EPISODE + s for s in ('.mkv', '.nfo', '.webp', '.en.vtt', '.info.json'))
        assert move.remove_old_dir

    def test_planning_changes_nothing(self, channel_dir, ydl):
        video = _legacy_video(channel_dir)
        before = sorted(os.walk(channel_dir))

        plan_channel(channel_dir, ydl)

        assert sorted(os.walk(channel_dir)) == before
        assert os.path.exists(video)

    def test_skips_video_without_info_json(self, channel_dir, ydl):
        _legacy_video(channel_dir, info=False)

        plan = plan_channel(channel_dir, ydl)

        assert plan.moves == []
        assert 'no readable .info.json' in plan.skipped[0][1]

    def test_skips_when_target_exists(self, channel_dir, ydl):
        _legacy_video(channel_dir)
        target_dir = os.path.join(channel_dir, 'Season 2021', NEW_EPISODE)
        os.makedirs(target_dir)
        open(os.path.join(target_dir, NEW_EPISODE + '.mkv'), 'w').close()

        plan = plan_channel(channel_dir, ydl)

        # The legacy copy is skipped instead of overwriting the existing file
        assert plan.moves == []
        assert any('target already exists' in reason for _p, reason in plan.skipped)

    def test_ignores_partial_downloads(self, channel_dir, ydl):
        video = _legacy_video(channel_dir)
        os.rename(video, video + '.part')

        assert plan_channel(channel_dir, ydl).moves == []

    def test_lists_files_without_a_video_as_leftovers(self, channel_dir, ydl):
        _legacy_video(channel_dir)
        orphan = _orphan_info(channel_dir)

        plan = plan_channel(channel_dir, ydl)

        assert len(plan.moves) == 1
        # The video's own sidecars move with it; season.nfo is not a leftover
        assert plan.leftovers == [orphan]

    def test_lists_leftovers_when_nothing_is_left_to_rename(self, channel_dir, ydl, tmp_path):
        _legacy_video(channel_dir)
        apply_plan(plan_channel(channel_dir, ydl), NFOService(str(tmp_path)))
        orphan = _orphan_info(channel_dir)

        plan = plan_channel(channel_dir, ydl)

        assert plan.moves == [] and plan.leftovers == [orphan]

    def test_skipped_video_keeps_its_files(self, channel_dir, ydl):
        video = _legacy_video(channel_dir, info=False)

        plan = plan_channel(channel_dir, ydl)

        assert plan.skipped and plan.leftovers == []
        assert os.path.exists(video)


class TestApplyPlan:
    def test_moves_files_and_regenerates_nfos(self, channel_dir, ydl, tmp_path):
        _legacy_video(channel_dir)
        plan = plan_channel(channel_dir, ydl)

        result = apply_plan(plan, NFOService(str(tmp_path)))

        assert result.moved == 1 and result.errors == []
        new_dir = os.path.join(channel_dir, 'Season 2021', NEW_EPISODE)
        assert sorted(os.listdir(new_dir)) == sorted(
            NEW_EPISODE + s for s in ('.mkv', '.nfo', '.webp', '.en.vtt', '.info.json'))
        # Old year folder (with only its season.nfo left) is gone
        assert sorted(os.listdir(channel_dir)) == ['Season 2021']

        episode = ET.parse(os.path.join(new_dir, NEW_EPISODE + '.nfo')).getroot()
        assert episode.find('season').text == '2021'
        assert episode.find('episode').text == '12071530'
        season = ET.parse(os.path.join(channel_dir, 'Season 2021', 'season.nfo')).getroot()
        assert season.find('seasonnumber').text == '2021'

    def test_second_run_is_noop(self, channel_dir, ydl, tmp_path):
        _legacy_video(channel_dir)
        apply_plan(plan_channel(channel_dir, ydl), NFOService(str(tmp_path)))

        plan = plan_channel(channel_dir, ydl)

        assert plan.moves == [] and plan.skipped == []
        assert plan.already_migrated == 1

    def test_keeps_legacy_year_folder_with_other_content(self, channel_dir, ydl, tmp_path):
        _legacy_video(channel_dir)
        open(os.path.join(channel_dir, '2021', 'notes.txt'), 'w').close()

        apply_plan(plan_channel(channel_dir, ydl), NFOService(str(tmp_path)))

        assert os.path.exists(os.path.join(channel_dir, '2021', 'notes.txt'))

    def test_leftovers_stay_without_leftovers_root(self, channel_dir, ydl, tmp_path):
        _legacy_video(channel_dir)
        orphan = _orphan_info(channel_dir)

        apply_plan(plan_channel(channel_dir, ydl), NFOService(str(tmp_path)))

        assert os.path.exists(orphan)
        assert os.path.exists(os.path.join(channel_dir, '2021', 'season.nfo'))

    def test_moves_leftovers_aside_and_removes_old_year_folder(self, channel_dir, ydl, tmp_path):
        _legacy_video(channel_dir)
        orphan = _orphan_info(channel_dir)
        leftovers_root = str(tmp_path / 'leftovers')

        result = apply_plan(plan_channel(channel_dir, ydl), NFOService(str(tmp_path)),
                            leftovers_root)

        assert result.moved == 1 and result.leftovers_moved == 1 and result.errors == []
        assert sorted(os.listdir(channel_dir)) == ['Season 2021']
        moved = os.path.join(leftovers_root, os.path.basename(channel_dir),
                             os.path.relpath(orphan, channel_dir))
        assert os.path.exists(moved)

    def test_failed_move_is_rolled_back(self, channel_dir, ydl, tmp_path):
        video = _legacy_video(channel_dir)
        plan = plan_channel(channel_dir, ydl)
        real_rename = os.rename
        calls = []

        def flaky_rename(src, dst):
            calls.append(src)
            if len(calls) == 3:
                raise OSError('disk hiccup')
            real_rename(src, dst)

        with patch('app.migrate_media_layout.os.rename', side_effect=flaky_rename):
            result = apply_plan(plan, NFOService(str(tmp_path)))

        assert result.moved == 0
        assert 'disk hiccup' in result.errors[0][1]
        # Every file is back where it started
        assert len(os.listdir(os.path.dirname(video))) == 5


class TestCli:
    @pytest.fixture
    def setup(self, db_session, tmp_path):
        media_dir = tmp_path / 'media'
        channel_dir = media_dir / 'Ms Rachel [UCabc]'
        channel_dir.mkdir(parents=True)
        video = _legacy_video(str(channel_dir))

        channel = Channel(url='https://www.youtube.com/@msrachel', name='Ms Rachel',
                          channel_id='UCabc', directory_path=str(channel_dir))
        db_session.add(channel)
        db_session.commit()
        db_session.add(Download(channel_id=channel.id, video_id='abcdefghijk',
                                title='Learn Colors', status='completed', file_path=video))
        db_session.commit()

        settings = SimpleNamespace(media_dir=str(media_dir))
        with patch('app.config.get_settings', return_value=settings), \
                patch('app.database.SessionLocal', return_value=db_session), \
                patch('app.nfo_service.get_nfo_service', return_value=NFOService(str(media_dir))), \
                patch('app.migrate_media_layout.os.geteuid', return_value=1000):
            yield SimpleNamespace(video=video, channel_dir=str(channel_dir), db=db_session)

    def test_dry_run_is_default_and_changes_nothing(self, setup, capsys):
        assert run([]) == 0

        out = capsys.readouterr().out
        assert 'RENAME Ms Rachel [UCabc]/2021/' in out
        assert f'-> Ms Rachel [UCabc]/Season 2021/{NEW_EPISODE}/{NEW_EPISODE}.mkv' in out
        assert 'Dry run: 1 video(s) would be renamed' in out
        assert os.path.exists(setup.video)

    def test_apply_moves_files_and_updates_database(self, setup, capsys):
        assert run(['--apply']) == 0

        new_path = os.path.join(setup.channel_dir, 'Season 2021', NEW_EPISODE, NEW_EPISODE + '.mkv')
        assert os.path.exists(new_path)
        assert not os.path.exists(setup.video)
        download = setup.db.query(Download).filter_by(video_id='abcdefghijk').one()
        assert download.file_path == new_path
        assert 'Migrated 1 of 1 video(s).' in capsys.readouterr().out

    def test_apply_refuses_while_downloads_run(self, setup, capsys):
        from app.models import ApplicationSettings
        setup.db.add(ApplicationSettings(key='scheduled_downloads_running', value='true'))
        setup.db.commit()

        assert run(['--apply']) == 2

        assert 'download run is in progress' in capsys.readouterr().out
        assert os.path.exists(setup.video)

    def test_apply_refuses_as_root(self, setup, capsys):
        with patch('app.migrate_media_layout.os.geteuid', return_value=0):
            assert run(['--apply']) == 2

        assert 'Refusing to --apply as root' in capsys.readouterr().out
        assert os.path.exists(setup.video)

    def test_dry_run_lists_leftovers(self, setup, capsys):
        orphan = _orphan_info(setup.channel_dir)

        assert run([]) == 0

        out = capsys.readouterr().out
        assert 'LEFTOVER Ms Rachel [UCabc]/2021/' in out
        assert '1 leftover file(s) in old year folders belong to no video' in out
        assert os.path.exists(orphan)

    def test_remove_leftovers_after_videos_were_migrated(self, setup, capsys):
        # The reported case: videos already moved, only leftovers remain
        assert run(['--apply']) == 0
        orphan = _orphan_info(setup.channel_dir)
        capsys.readouterr()

        assert run(['--apply']) == 0
        assert 'Nothing to migrate.' in capsys.readouterr().out
        assert os.path.exists(orphan)

        assert run(['--apply', '--remove-leftovers']) == 0

        out = capsys.readouterr().out
        assert 'Moved 1 of 1 leftover file(s)' in out
        assert not os.path.exists(orphan)
        assert sorted(os.listdir(setup.channel_dir)) == ['Season 2021']
        leftovers = os.path.join(os.path.dirname(setup.channel_dir), '.migrate-leftovers')
        moved = [os.path.join(root, f) for root, _d, files in os.walk(leftovers) for f in files]
        assert [os.path.basename(p) for p in moved] == [os.path.basename(orphan)]

    def test_channel_filter(self, setup, capsys):
        assert run(['--channel', '999']) == 0
        assert 'No channel folders found.' in capsys.readouterr().out

    def test_dry_run_and_apply_are_exclusive(self, setup):
        with pytest.raises(SystemExit):
            run(['--dry-run', '--apply'])
