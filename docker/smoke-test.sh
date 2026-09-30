#!/bin/sh
# Smoke test for the container entrypoint (PUID/PGID/UMASK/TZ handling).
#
# Usage: docker/smoke-test.sh <image>
#
# Starts the image the way users do and checks the behaviour documented in
# docs/DEPLOYMENT.md: the app runs as PUID/PGID with the requested umask and a
# writable HOME, files already in media/ keep their owner, and invalid
# settings fail clearly. Run by .github/workflows/docker-smoke.yml.

set -eu

IMAGE=${1:?usage: $0 <image>}
WORK=$(mktemp -d)
NAME=cfw-smoke-$$
FAILED=0

cleanup() {
    docker rm -f "$NAME" "$NAME-tz" >/dev/null 2>&1 || true
    # Files are owned by other UIDs; remove them from inside a container
    docker run --rm --entrypoint sh -v "$WORK:/w" "$IMAGE" -c 'rm -rf /w/*' >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap cleanup EXIT

pass() { echo "PASS: $*"; }
fail() { echo "FAIL: $*"; FAILED=1; }
check() { # check <description> <expected> <actual>
    if [ "$2" = "$3" ]; then pass "$1 ($3)"; else fail "$1: expected '$2', got '$3'"; fi
}

mkdir -p "$WORK/data" "$WORK/media" "$WORK/temp"
# A file already in the library, owned by someone else
docker run --rm --entrypoint sh -v "$WORK/media:/app/media" "$IMAGE" \
    -c 'touch /app/media/existing.mkv && chown 1234:1234 /app/media/existing.mkv'

echo "--- PUID=1500 PGID=1500 UMASK=002 TZ=America/Chicago"
docker run -d --name "$NAME" \
    -e PUID=1500 -e PGID=1500 -e UMASK=002 -e TZ=America/Chicago \
    -v "$WORK/data:/app/data" -v "$WORK/media:/app/media" -v "$WORK/temp:/app/temp" \
    "$IMAGE" >/dev/null

i=0
until docker exec "$NAME" curl -sf http://localhost:8000/health >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 90 ]; then
        docker logs "$NAME" 2>&1 | tail -40
        fail "backend did not become healthy within 180s"
        exit 1
    fi
    sleep 2
done
pass "backend healthy"

PID=$(docker exec "$NAME" pgrep -f 'uvicorn main:app' | head -1)
check "backend UID" "1500" "$(docker exec "$NAME" stat -c %u "/proc/$PID")"
check "backend umask" "0002" "$(docker exec "$NAME" awk '/^Umask/ {print $2}' "/proc/$PID/status")"
check "backend HOME" "HOME=/home/appuser" \
    "$(docker exec -u appuser "$NAME" sh -c "tr '\0' '\n' < /proc/$PID/environ | grep '^HOME='")"
check "database owner" "1500:1500" "$(docker exec "$NAME" stat -c %u:%g /app/data/app.db)"
check "existing media file keeps its owner" "1234:1234" \
    "$(docker exec "$NAME" stat -c %u:%g /app/media/existing.mkv)"
TZ_ABBR=$(docker exec "$NAME" date +%Z)
case "$TZ_ABBR" in CST|CDT) pass "timezone ($TZ_ABBR)" ;; *) fail "timezone: expected CST/CDT, got '$TZ_ABBR'" ;; esac
if docker logs "$NAME" 2>&1 | grep -q CRIT; then fail "supervisord logged CRIT"; else pass "no supervisord CRIT"; fi

echo "--- invalid values stop the container"
for env in PUID=abc PGID=x UMASK=999; do
    code=0
    docker run --rm -e "$env" "$IMAGE" true >/dev/null 2>&1 || code=$?
    check "$env exits with error" "1" "$code"
done

echo "--- unknown TZ falls back to UTC"
out=$(docker run --rm -e TZ=Mars/Olympus "$IMAGE" sh -c 'date +%Z' 2>&1)
case "$out" in
    *"Unknown timezone TZ='Mars/Olympus'"*UTC) pass "unknown TZ falls back to UTC" ;;
    *) fail "unknown TZ: got: $out" ;;
esac

exit "$FAILED"
