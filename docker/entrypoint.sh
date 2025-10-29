#!/bin/sh
# Entrypoint script for ChannelFinWatcher container
# Initializes directories and starts services

set -e

echo "==================================="
echo "ChannelFinWatcher Starting..."
echo "==================================="

# Ensure required directories exist
echo "Initializing directories..."
mkdir -p /app/data /app/media /app/temp

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

echo "==================================="
echo "Starting services..."
echo "==================================="

# Execute the CMD
exec "$@"
