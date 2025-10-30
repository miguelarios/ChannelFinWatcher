#!/bin/sh
# Entrypoint script for ChannelFinWatcher container
# Initializes directories and starts services

set -e

echo "==================================="
echo "ChannelFinWatcher Starting..."
echo "==================================="

# Handle UID/GID changes if specified
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "User configuration:"
echo "  - PUID: $PUID"
echo "  - PGID: $PGID"

# Check if we need to change the user's UID/GID
CURRENT_UID=$(id -u appuser)
CURRENT_GID=$(id -g appuser)

if [ "$CURRENT_UID" != "$PUID" ] || [ "$CURRENT_GID" != "$PGID" ]; then
    echo "Updating appuser UID:GID from $CURRENT_UID:$CURRENT_GID to $PUID:$PGID"

    # Change the GID first
    groupmod -o -g "$PGID" appuser

    # Then change the UID
    usermod -o -u "$PUID" appuser

    # Fix ownership of existing files
    echo "Updating file permissions (this may take a moment)..."
    chown -R appuser:appuser /app /home/appuser
fi

# Ensure required directories exist
echo "Initializing directories..."
mkdir -p /app/data /app/media /app/temp

# Set ownership of volume mount points
chown appuser:appuser /app/data /app/media /app/temp

# Check if database needs initialization
if [ ! -f /app/data/app.db ]; then
    echo "Database not found. It will be created on first run."
fi

# Display configuration
echo "Configuration:"
echo "  - Data directory: /app/data"
echo "  - Media directory: /app/media"
echo "  - Temp directory: /app/temp"
echo "  - Timezone: ${TZ:-UTC}"
echo "  - Running as: $(id appuser)"

echo "==================================="
echo "Starting services..."
echo "==================================="

# Execute the CMD
exec "$@"
