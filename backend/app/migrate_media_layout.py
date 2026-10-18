"""
Migrate downloaded videos to the current media layout (see app/media_layout.py).

Older versions of the app wrote:
    Channel [UCxxxx]/2021/Channel - 20211207 - Title [id]/Channel - 20211207 - Title [id].mkv

The current layout is:
    Channel [UCxxxx]/Season 2021/S2021E12071530 - Title [id]/S2021E12071530 - Title [id].mkv

This tool renames existing videos (and every sidecar file: .nfo, .info.json,
thumbnails, subtitles) into the current layout, updates the file paths stored
in the database, and regenerates the episode/season NFO files so Jellyfin gets
the new <season>/<episode> numbers.

Usage (the `cfw` wrapper runs it as the app's user, so new folders stay writable):
    docker exec -it channelfinwatcher cfw migrate-layout            # dry run
    docker exec -it channelfinwatcher cfw migrate-layout --apply    # rename
    docker exec -it channelfinwatcher cfw migrate-layout --apply --remove-leftovers

Leftovers are files in the old year folders that belong to no video file,
mostly .info.json files yt-dlp wrote for downloads that later failed. The
app never reads them. The dry run lists them; --remove-leftovers moves them
to <media>/.migrate-leftovers/<timestamp>/ (delete that folder once you
have checked it) so the old year folders can be removed.

Why a CLI instead of migrating automatically on startup?
- Renaming a whole library is a one-time, hard-to-undo change; a dry run lets
  you review every rename before anything moves.
- Jellyfin treats renamed files as new items, so you choose when to do it.

Safety:
- Default is a dry run; nothing changes without --apply.
- --apply holds the "scheduled_downloads" lock, so no download runs meanwhile.
- The target name is computed by yt-dlp from the video's .info.json with the
  same template new downloads use, so migrated and new files match exactly.
- Nothing is overwritten: a video whose target already exists is skipped.
- Running it again is safe; videos already in the current layout are skipped.
- Leftovers are moved aside, never deleted, and only with --remove-leftovers.
"""

import argparse
import json
import logging
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

import yt_dlp

from app.media_layout import (
    EPISODE_RELATIVE_TEMPLATE,
    episode_numbers,
    parse_season_dir,
)

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = ('.mkv', '.mp4', '.webm', '.m4v', '.avi', '.mov')
VIDEO_ID_RE = re.compile(r'\[([A-Za-z0-9_-]{11})\]$')
LEFTOVERS_DIR = '.migrate-leftovers'  # under the media folder; Jellyfin skips dot folders


@dataclass
class VideoMove:
    """One video (plus its sidecar files) moving to its new location."""
    video_id: str
    old_video_path: str
    new_video_path: str
    # (source, destination) for every file/folder that moves
    file_moves: List[Tuple[str, str]]
    # True when the old folder held only this video, so it is removed afterwards
    remove_old_dir: bool


@dataclass
class ChannelPlan:
    """Everything the migration would do for one channel folder."""
    channel_dir: str
    moves: List[VideoMove] = field(default_factory=list)
    already_migrated: int = 0
    skipped: List[Tuple[str, str]] = field(default_factory=list)  # (path, reason)
    # Files in old year folders that belong to no video and stay behind
    leftovers: List[str] = field(default_factory=list)


@dataclass
class ChannelResult:
    """What actually happened when a ChannelPlan was applied."""
    moved: int = 0
    leftovers_moved: int = 0
    errors: List[Tuple[str, str]] = field(default_factory=list)  # (path, reason)
    new_paths: Dict[str, str] = field(default_factory=dict)  # video_id -> new path


# =========================================================================
# PLANNING (read-only)
# =========================================================================

def _find_video_files(channel_dir: str) -> List[Tuple[str, str]]:
    """Return (video_id, path) for every finished video under channel_dir."""
    videos = []
    for root, _dirs, files in os.walk(channel_dir):
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext.lower() not in VIDEO_EXTENSIONS:
                continue  # skips .part, .info.json, .nfo, images, subtitles
            match = VIDEO_ID_RE.search(stem)
            if match:
                videos.append((match.group(1), os.path.join(root, name)))
    return sorted(videos, key=lambda v: v[1])


def _legacy_season_dirs(channel_dir: str) -> List[str]:
    """Bare-year season folders ("2021") written by older versions."""
    return sorted(
        os.path.join(channel_dir, entry) for entry in os.listdir(channel_dir)
        if entry.isdigit() and parse_season_dir(entry)
        and os.path.isdir(os.path.join(channel_dir, entry))
    )


def _is_video(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS


def _find_leftovers(channel_dir: str, moves: List[VideoMove]) -> List[str]:
    """
    Files in the old year folders that will still be there after `moves`.

    A folder that keeps a video (one that is skipped) is left alone entirely,
    so a skipped video never loses its sidecars. Each year folder's own
    season.nfo is not counted; it goes when the folder is removed.
    """
    moving = {os.path.normpath(src) for move in moves for src, _dst in move.file_moves}
    leftovers = []
    for year_dir in _legacy_season_dirs(channel_dir):
        for root, dirs, files in os.walk(year_dir):
            dirs[:] = sorted(d for d in dirs
                             if os.path.normpath(os.path.join(root, d)) not in moving)
            staying = [name for name in files
                       if os.path.normpath(os.path.join(root, name)) not in moving]
            if any(_is_video(name) for name in staying):
                dirs[:] = []  # a video stays here; keep the whole folder
                continue
            leftovers.extend(
                os.path.join(root, name) for name in sorted(staying)
                if not (root == year_dir and name == 'season.nfo')
            )
    return leftovers


def _load_info(info_path: str) -> Optional[dict]:
    try:
        with open(info_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def plan_channel(channel_dir: str, ydl: yt_dlp.YoutubeDL) -> ChannelPlan:
    """
    Work out which videos in channel_dir need renaming, without touching disk.

    Args:
        channel_dir: Absolute path of the channel folder
        ydl: YoutubeDL instance used only to evaluate the filename template
    """
    plan = ChannelPlan(channel_dir=channel_dir)
    videos = _find_video_files(channel_dir)

    # Folder -> number of videos in it. A folder holding a single video is that
    # video's own folder (the normal layout) and moves as a whole.
    videos_per_dir: Dict[str, int] = {}
    for _video_id, path in videos:
        folder = os.path.dirname(path)
        videos_per_dir[folder] = videos_per_dir.get(folder, 0) + 1

    claimed_targets = set()

    for video_id, old_path in videos:
        old_dir = os.path.dirname(old_path)
        old_stem, ext = os.path.splitext(os.path.basename(old_path))

        info = _load_info(os.path.join(old_dir, old_stem + '.info.json'))
        if not info:
            plan.skipped.append((old_path, 'no readable .info.json next to the video'))
            continue
        if info.get('id') != video_id:
            plan.skipped.append((old_path, '.info.json belongs to a different video'))
            continue
        if episode_numbers(info) is None:
            plan.skipped.append((old_path, '.info.json has no upload_date'))
            continue

        # Same template and sanitization yt-dlp uses for new downloads.
        # 'ext' comes from the real file (info.json may list a pre-merge format).
        relative = ydl.prepare_filename({**info, 'ext': ext.lstrip('.')},
                                        outtmpl=EPISODE_RELATIVE_TEMPLATE)
        new_path = os.path.join(channel_dir, relative)

        if os.path.normpath(new_path) == os.path.normpath(old_path):
            plan.already_migrated += 1
            continue
        if new_path in claimed_targets:
            plan.skipped.append((old_path, f'another video already maps to {relative}'))
            continue

        new_dir = os.path.dirname(new_path)
        new_stem = os.path.splitext(os.path.basename(new_path))[0]
        own_folder = videos_per_dir[old_dir] == 1 and old_dir != channel_dir

        file_moves = []
        for entry in sorted(os.listdir(old_dir)):
            if entry.startswith(old_stem):
                file_moves.append((os.path.join(old_dir, entry),
                                   os.path.join(new_dir, new_stem + entry[len(old_stem):])))
            elif own_folder:
                # Unrelated file in the video's own folder: keep its name
                file_moves.append((os.path.join(old_dir, entry),
                                   os.path.join(new_dir, entry)))

        file_moves = [(src, dst) for src, dst in file_moves
                      if os.path.normpath(src) != os.path.normpath(dst)]
        conflicts = [dst for _src, dst in file_moves if os.path.lexists(dst)]
        if conflicts:
            plan.skipped.append((old_path, f'target already exists: {conflicts[0]}'))
            continue

        claimed_targets.add(new_path)
        plan.moves.append(VideoMove(
            video_id=video_id,
            old_video_path=old_path,
            new_video_path=new_path,
            file_moves=file_moves,
            remove_old_dir=own_folder and os.path.normpath(old_dir) != os.path.normpath(new_dir),
        ))

    plan.leftovers = _find_leftovers(channel_dir, plan.moves)
    return plan


# =========================================================================
# APPLYING (changes disk)
# =========================================================================

def _move_video(move: VideoMove) -> None:
    """Move one video's files; on failure, put already-moved files back."""
    done: List[Tuple[str, str]] = []
    try:
        for src, dst in move.file_moves:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.lexists(dst):
                raise FileExistsError(f'target already exists: {dst}')
            os.rename(src, dst)
            done.append((src, dst))
    except Exception:
        for src, dst in reversed(done):
            try:
                os.rename(dst, src)
            except OSError as rollback_error:
                logger.error(f'Could not restore {dst} -> {src}: {rollback_error}')
        raise

    if move.remove_old_dir:
        old_dir = os.path.dirname(move.old_video_path)
        try:
            os.rmdir(old_dir)  # only succeeds if empty
        except OSError:
            logger.warning(f'Old folder not empty, left in place: {old_dir}')


def _move_leftovers(channel_dir: str, leftovers: List[str], leftovers_root: str) -> int:
    """Move leftover files to leftovers_root/<channel folder>/..., keeping their paths."""
    target_base = os.path.join(leftovers_root, os.path.basename(channel_dir))
    moved = 0
    for src in leftovers:
        if not os.path.lexists(src):
            continue
        dst = os.path.join(target_base, os.path.relpath(src, channel_dir))
        if os.path.lexists(dst):
            raise FileExistsError(f'target already exists: {dst}')
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.move(src, dst)
        moved += 1
    return moved


def _remove_empty_legacy_season_dirs(channel_dir: str) -> None:
    """Remove bare-year season folders ("2021") left holding only season.nfo."""
    for path in _legacy_season_dirs(channel_dir):
        # Drop empty video folders first (left behind once leftovers move out)
        for root, _dirs, _files in os.walk(path, topdown=False):
            if root != path and not os.listdir(root):
                os.rmdir(root)
        remaining = os.listdir(path)
        if set(remaining) <= {'season.nfo'}:
            for name in remaining:
                os.remove(os.path.join(path, name))
            os.rmdir(path)


def apply_plan(plan: ChannelPlan, nfo_service,
               leftovers_root: Optional[str] = None) -> ChannelResult:
    """
    Carry out a ChannelPlan: move files, regenerate NFOs, tidy old folders.

    Args:
        plan: Result of plan_channel
        nfo_service: Used to rewrite episode NFOs and create season NFOs
        leftovers_root: When set, plan.leftovers are moved under this folder
            before the old year folders are tidied; otherwise they stay put.

    The caller is responsible for updating the database with result.new_paths.
    """
    result = ChannelResult()
    season_dirs = set()

    for move in plan.moves:
        try:
            _move_video(move)
        except Exception as e:
            result.errors.append((move.old_video_path, str(e)))
            continue

        result.moved += 1
        result.new_paths[move.video_id] = move.new_video_path
        season_dirs.add(os.path.dirname(os.path.dirname(move.new_video_path)))

        # Episode NFO was moved with the video; rewrite it with season/episode tags
        success, error = nfo_service.generate_episode_nfo(move.new_video_path, None)
        if not success:
            result.errors.append((move.new_video_path, f'episode NFO: {error}'))

    for season_dir in sorted(season_dirs):
        if not os.path.exists(os.path.join(season_dir, 'season.nfo')):
            success, error = nfo_service.generate_season_nfo(season_dir)
            if not success:
                result.errors.append((season_dir, f'season NFO: {error}'))

    if leftovers_root and plan.leftovers:
        try:
            result.leftovers_moved = _move_leftovers(
                plan.channel_dir, plan.leftovers, leftovers_root)
        except OSError as e:
            result.errors.append((plan.channel_dir, f'moving leftovers: {e}'))

    try:
        _remove_empty_legacy_season_dirs(plan.channel_dir)
    except OSError as e:
        result.errors.append((plan.channel_dir, f'cleaning old season folders: {e}'))

    return result


# =========================================================================
# CLI
# =========================================================================

def _channel_dirs(db, media_dir: str) -> List[Tuple[object, str]]:
    """(channel, folder) for every channel folder that exists on disk."""
    from app.models import Channel
    from app.utils import channel_dir_name

    pairs = []
    for channel in db.query(Channel).order_by(Channel.name).all():
        candidates = []
        if channel.channel_id:
            candidates.append(os.path.join(media_dir, channel_dir_name(channel)))
        if channel.directory_path:
            candidates.append(channel.directory_path)
        seen = set()
        for path in candidates:
            path = os.path.normpath(path)
            if path not in seen and os.path.isdir(path):
                seen.add(path)
                pairs.append((channel, path))
    return pairs


def _print_plan(plan: ChannelPlan, media_dir: str) -> None:
    def rel(path: str) -> str:
        return os.path.relpath(path, media_dir)

    for move in plan.moves:
        print(f'  RENAME {rel(move.old_video_path)}')
        print(f'      -> {rel(move.new_video_path)}')
    for path, reason in plan.skipped:
        print(f'  SKIP   {rel(path)}: {reason}')
    for path in plan.leftovers:
        print(f'  LEFTOVER {rel(path)}')


def run(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog='python -m app.migrate_media_layout',
        description='Rename downloaded videos into the Jellyfin season/episode layout.',
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--dry-run', action='store_true',
                      help='only print what would change (the default)')
    mode.add_argument('--apply', action='store_true',
                      help='perform the renames')
    parser.add_argument('--channel', type=int, metavar='ID',
                        help='only migrate the channel with this database ID')
    parser.add_argument('--remove-leftovers', action='store_true',
                        help=f'with --apply, move files in old year folders that belong '
                             f'to no video into <media>/{LEFTOVERS_DIR}/')
    args = parser.parse_args(argv)

    from app.config import get_settings
    from app.database import SessionLocal
    from app.models import Download
    from app.nfo_service import get_nfo_service
    from app.overlap_prevention import JobAlreadyRunningError, scheduler_lock

    media_dir = get_settings().media_dir
    ydl = yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True})
    db = SessionLocal()

    try:
        channel_dirs = [(c, d) for c, d in _channel_dirs(db, media_dir)
                        if args.channel is None or c.id == args.channel]
        if not channel_dirs:
            print('No channel folders found.')
            return 0

        plans = []
        for channel, channel_dir in channel_dirs:
            plan = plan_channel(channel_dir, ydl)
            plans.append((channel, plan))
            print(f'\n{channel.name} (id {channel.id}): {len(plan.moves)} to rename, '
                  f'{plan.already_migrated} already migrated, {len(plan.skipped)} skipped, '
                  f'{len(plan.leftovers)} leftover file(s)')
            _print_plan(plan, media_dir)

        total_moves = sum(len(p.moves) for _c, p in plans)
        total_skipped = sum(len(p.skipped) for _c, p in plans)
        total_leftovers = sum(len(p.leftovers) for _c, p in plans)
        leftovers_hint = (f'{total_leftovers} leftover file(s) in old year folders belong to '
                          f'no video. --apply --remove-leftovers moves them to '
                          f'{os.path.join(media_dir, LEFTOVERS_DIR)}/.')

        if not args.apply:
            print(f'\nDry run: {total_moves} video(s) would be renamed, '
                  f'{total_skipped} skipped. Nothing was changed.')
            if total_moves:
                print('Run again with --apply to perform the renames.')
            if total_leftovers:
                print(leftovers_hint)
            return 0

        remove_leftovers = args.remove_leftovers and total_leftovers > 0
        if not total_moves and not remove_leftovers:
            print('\nNothing to migrate.')
            if total_leftovers:
                print(leftovers_hint)
            return 0

        # Folders and NFOs created as root would be unwritable for the app,
        # which runs as appuser, and later downloads into them would fail
        if hasattr(os, 'geteuid') and os.geteuid() == 0:
            print('\nRefusing to --apply as root: new folders would not be writable by the app.'
                  '\nRe-run with: docker exec -it channelfinwatcher cfw migrate-layout --apply')
            return 2

        nfo_service = get_nfo_service()
        leftovers_root = None
        if remove_leftovers:
            leftovers_root = os.path.join(
                media_dir, LEFTOVERS_DIR, datetime.now().strftime('%Y%m%d-%H%M%S'))
        total_moved = 0
        total_leftovers_moved = 0
        all_errors: List[Tuple[str, str]] = []

        try:
            with scheduler_lock(db, 'scheduled_downloads'):
                for _channel, plan in plans:
                    result = apply_plan(plan, nfo_service, leftovers_root)
                    total_moved += result.moved
                    total_leftovers_moved += result.leftovers_moved
                    all_errors.extend(result.errors)

                    # Keep the database pointing at the moved files
                    for video_id, new_path in result.new_paths.items():
                        download = db.query(Download).filter(Download.video_id == video_id).first()
                        if download:
                            download.file_path = new_path
                    db.commit()
        except JobAlreadyRunningError:
            print('\nA download run is in progress. Wait for it to finish, then run --apply again.')
            return 2

        print()
        if total_moves:
            print(f'Migrated {total_moved} of {total_moves} video(s).')
        if remove_leftovers:
            print(f'Moved {total_leftovers_moved} of {total_leftovers} leftover file(s) to '
                  f'{leftovers_root}/. Delete that folder once you have checked it.')
        elif total_leftovers:
            print(leftovers_hint)
        for path, reason in all_errors:
            print(f'  ERROR  {os.path.relpath(path, media_dir)}: {reason}')
        if total_moved:
            print('Now run a library scan in Jellyfin.')
        return 1 if all_errors else 0
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(message)s')
    sys.exit(run())


if __name__ == '__main__':
    main()
