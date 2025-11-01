#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧪 Testing docker-compose-dev.yml${NC}"
echo ""

# Cleanup function
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    docker compose -f docker-compose.dev.yml down -v 2>/dev/null || true
    rm -rf test/ 2>/dev/null || true
}

# Set trap to cleanup on exit
trap cleanup EXIT

# Step 1: Create test directories
echo -e "${YELLOW}📁 Creating test directories...${NC}"
mkdir -p test/data test/media test/temp
chmod -R 755 test/

# Step 2: Start services
echo -e "${YELLOW}🚀 Starting services...${NC}"
docker compose -f docker-compose.dev.yml up -d

# Step 3: Wait for services to be ready
echo -e "${YELLOW}⏳ Waiting for backend to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0

while ! curl -f http://localhost:8001/health > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Backend failed to start within 60 seconds${NC}"
        echo -e "${YELLOW}Backend logs:${NC}"
        docker compose -f docker-compose.dev.yml logs backend
        exit 1
    fi
    sleep 2
done

echo -e "${GREEN}✅ Backend is ready${NC}"

echo -e "${YELLOW}⏳ Waiting for frontend to be ready...${NC}"
RETRY_COUNT=0

while ! curl -f http://localhost:3333 > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ Frontend failed to start within 60 seconds${NC}"
        echo -e "${YELLOW}Frontend logs:${NC}"
        docker compose -f docker-compose.dev.yml logs frontend
        exit 1
    fi
    sleep 2
done

echo -e "${GREEN}✅ Frontend is ready${NC}"
echo ""

# Step 4: Test API endpoints
echo -e "${YELLOW}🧪 Testing API endpoints...${NC}"

# Test health endpoint
echo -n "  Testing /health... "
if curl -f http://localhost:8001/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    exit 1
fi

# Test channels endpoint
echo -n "  Testing /api/v1/channels... "
if curl -f http://localhost:8001/api/v1/channels > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    exit 1
fi

# Test settings endpoint
echo -n "  Testing /api/v1/settings/default-video-limit... "
if curl -f http://localhost:8001/api/v1/settings/default-video-limit > /dev/null 2>&1; then
    echo -e "${GREEN}✅${NC}"
else
    echo -e "${RED}❌${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ All tests passed!${NC}"
echo ""
echo -e "${YELLOW}Services are running:${NC}"
echo "  Backend:  http://localhost:8001"
echo "  Frontend: http://localhost:3333"
echo ""
echo "To view logs: docker compose -f docker-compose.dev.yml logs -f"
echo "To stop: docker compose -f docker-compose.dev.yml down"
echo ""

# Ask if user wants to keep services running
read -p "Keep services running? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    cleanup
fi
