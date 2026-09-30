#!/bin/sh
# Entrypoint script for ChannelFinWatcher container
#
# Follows the linuxserver.io conventions for self-hosted images:
#   PUID / PGID  run the app as this host user/group, so files it writes are
#                owned by you instead of root (find yours with `id`)
#   TZ           timezone for the scheduler, logs and timestamps
#   UMASK        permission mask for files the app creates (default 022)
#
# Runs as root only long enough to set up the user and folders; supervisord
# then starts the backend and frontend as `appuser`.

set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}
UMASK=${UMASK:-022}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

# --- Validate settings ------------------------------------------------------
case "$PUID" in ''|*[!0-9]*) fail "PUID must be a number, got '$PUID'";; esac
case "$PGID" in ''|*[!0-9]*) fail "PGID must be a number, got '$PGID'";; esac
case "$UMASK" in
    [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
    *) fail "UMASK must be an octal value like 022 or 002, got '$UMASK'";;
esac

# An unknown TZ would make the scheduler fail to start; fall back to UTC
if [ -n "$TZ" ] && [ ! -f "/usr/share/zoneinfo/$TZ" ]; then
    echo "WARNING: Unknown timezone TZ='$TZ', falling back to UTC." >&2
    echo "         Use a name from https://en.wikipedia.org/wiki/List_of_tz_database_time_zones" >&2
    unset TZ
fi

# Applies to this script and supervisord; each app program also sets it from
# the environment (see supervisord.conf)
export UMASK
umask "$UMASK"

# --- Map appuser to PUID/PGID -----------------------------------------------
CURRENT_UID=$(id -u appuser)
CURRENT_GID=$(id -g appuser)

if [ "$CURRENT_UID" != "$PUID" ] || [ "$CURRENT_GID" != "$PGID" ]; then
    echo "Updating appuser UID:GID from $CURRENT_UID:$CURRENT_GID to $PUID:$PGID"
    groupmod -o -g "$PGID" appuser
    usermod -o -u "$PUID" appuser

    # Only the app's own files. The media library is deliberately left alone:
    # it can be huge, and other apps (Jellyfin, a NAS share) may rely on
    # its current ownership.
    chown -R appuser:appuser /app/backend /app/frontend /home/appuser
fi

# --- Folders ------------------------------------------------------------------
mkdir -p /app/data /app/media /app/temp

# data/ (database, config, cookies) and temp/ (partial downloads) belong to
# the app, so they are always handed to appuser, like /config in
# linuxserver.io images. Non-fatal so a read-only or root-squashed share
# gives a clear warning instead of a crash loop.
chown -R appuser:appuser /app/data /app/temp \
    || echo "WARNING: Could not set ownership of /app/data or /app/temp to $PUID:$PGID" >&2

# media/: fix only the top-level folder, and only if appuser can't write to
# it (e.g. Docker created the host folder as root). Never recurse.
if ! setpriv --reuid=appuser --regid=appuser --init-groups test -w /app/media; then
    chown appuser:appuser /app/media \
        || echo "WARNING: /app/media is not writable by $PUID:$PGID; downloads will fail." >&2
fi

if [ ! -f /app/data/app.db ]; then
    echo "Database not found. It will be created on first run."
fi

# --- Banner -------------------------------------------------------------------
echo "───────────────────────────────────────"
echo "ChannelFinWatcher"
echo "───────────────────────────────────────"
echo "User UID:    $(id -u appuser)"
echo "User GID:    $(id -g appuser)"
echo "Umask:       $UMASK"
echo "Timezone:    ${TZ:-UTC}"
echo "Data:        /app/data"
echo "Media:       /app/media"
echo "Temp:        /app/temp"
echo "───────────────────────────────────────"

exec "$@"
