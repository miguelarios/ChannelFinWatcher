# CI/CD Pipeline Explained

This document explains how the automated build and deployment system works for ChannelFinWatcher.

## Overview: From Code to Deployment

```
You push code to GitHub
         ↓
GitHub Actions automatically triggered
         ↓
Docker image built and tested
         ↓
Image pushed to GitHub Container Registry (GHCR)
         ↓
Users pull and run the pre-built image
```

## What is GitHub Actions?

**GitHub Actions** is a CI/CD (Continuous Integration/Continuous Deployment) platform built into GitHub.

**Why we use it:**
- **Automatic**: Runs automatically when you push code
- **Free**: Unlimited for public repositories
- **Integrated**: Built into GitHub, no third-party service needed
- **Powerful**: Can build, test, and deploy automatically

## What is GitHub Container Registry (GHCR)?

**GHCR** is GitHub's Docker image hosting service.

**Why we use it instead of Docker Hub:**
- **Free**: No rate limits or payment required
- **Integrated**: Uses GitHub authentication
- **Convenient**: Same place as your code
- **Private option**: Can make images private if needed

**Your image URL:**
```
ghcr.io/miguelarios/channelfinwatcher:latest
```

## The Workflow File Explained

Location: `.github/workflows/docker-publish.yml`

### Trigger Conditions

```yaml
on:
  push:
    branches:
      - main
    tags:
      - 'v*.*.*'
  pull_request:
    branches:
      - main
  workflow_dispatch:
```

**What triggers the workflow:**

1. **Push to main branch** → Builds and tags as `latest`
2. **Creating a git tag** (e.g., `v1.0.0`) → Builds and tags as `1.0.0`
3. **Pull request** → Builds to test (doesn't publish)
4. **Manual trigger** → You can run it manually from GitHub UI

### The Build Process (Step by Step)

#### Step 1: Checkout Code
```yaml
- name: Checkout repository
  uses: actions/checkout@v4
```
Downloads your repository code so the workflow can access it.

#### Step 2: Set Up Docker Buildx
```yaml
- name: Set up Docker Buildx
  uses: docker/setup-buildx-action@v3
```
**What is Buildx?**
- Enhanced Docker build engine
- Supports multi-platform builds (AMD64 and ARM64)
- Enables build caching for faster builds

**Why multi-platform?**
- Most servers use `linux/amd64` (Intel/AMD processors)
- Some devices use `linux/arm64` (Raspberry Pi, Apple Silicon)
- Building both means your image works everywhere

#### Step 3: Login to GHCR
```yaml
- name: Log in to GitHub Container Registry
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```
**Authentication:**
- Uses GitHub's built-in authentication
- `GITHUB_TOKEN` is automatically provided (no setup needed)
- Only logs in if publishing (skips for PRs)

#### Step 4: Extract Metadata
```yaml
- name: Extract metadata (tags, labels)
  id: meta
  uses: docker/metadata-action@v5
  with:
    images: ghcr.io/miguelarios/channelfinwatcher
    tags: |
      type=raw,value=latest,enable={{is_default_branch}}
      type=semver,pattern={{version}}
      type=semver,pattern={{major}}.{{minor}}
      type=sha,prefix={{branch}}-
```

**Tag generation examples:**

| Action | Generated Tags |
|--------|---------------|
| Push to main | `latest` |
| Tag `v1.0.0` | `1.0.0`, `1.0`, `latest` |
| Tag `v2.1.3` | `2.1.3`, `2.1`, `latest` |
| Push to branch | `feature-branch-abc1234` |

**Why multiple tags?**
- `latest`: Always get the newest version
- `1.0.0`: Pin to exact version
- `1.0`: Get latest patch (1.0.1, 1.0.2, etc.)

#### Step 5: Build and Push
```yaml
- name: Build and push Docker image
  uses: docker/build-push-action@v5
  with:
    context: .
    file: ./Dockerfile
    push: ${{ github.event_name != 'pull_request' }}
    tags: ${{ steps.meta.outputs.tags }}
    labels: ${{ steps.meta.outputs.labels }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
    platforms: linux/amd64,linux/arm64
```

**Key features:**

**Caching:**
- `cache-from: type=gha` - Use cached layers from previous builds
- `cache-to: type=gha,mode=max` - Save all layers for next build
- **Result**: First build ~10 minutes, subsequent builds ~2 minutes

**Multi-platform:**
- Builds once for Intel/AMD processors (`linux/amd64`)
- Builds again for ARM processors (`linux/arm64`)
- Both stored in same image tag

**Conditional push:**
- Pull requests: Build only (test it works)
- Main branch/tags: Build and publish

## Your Development Workflow

### Regular Development

1. **Make changes locally**
```bash
# Edit code, test with docker-compose.dev.yml
docker compose -f docker-compose.dev.yml up
```

2. **Commit and push to main**
```bash
git add .
git commit -m "feat: add new feature"
git push origin main
```

3. **GitHub Actions automatically:**
   - Detects the push
   - Starts building Docker image
   - Runs the build (takes ~5-10 minutes)
   - Publishes to `ghcr.io/miguelarios/channelfinwatcher:latest`

4. **Users can now update:**
```bash
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Creating a Release

When you're ready to mark a stable version:

```bash
# Tag the release
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

**What happens:**
- GitHub Actions builds the image
- Creates multiple tags: `1.0.0`, `1.0`, `latest`
- Users can now pin to version:
  ```yaml
  image: ghcr.io/miguelarios/channelfinwatcher:1.0.0
  ```

### Viewing Build Status

**In GitHub:**
1. Go to your repository
2. Click "Actions" tab
3. See all workflow runs

**Build status indicators:**
- ✅ Green check: Build successful
- ❌ Red X: Build failed
- 🟡 Yellow dot: Currently building
- ⏸️ Gray: Cancelled

**Viewing logs:**
- Click on any workflow run
- Click "build-and-push" job
- Expand each step to see detailed logs

## Understanding the Multi-Stage Dockerfile

Location: `/Dockerfile`

### Stage 1: Build Frontend
```dockerfile
FROM node:18-alpine AS frontend-builder
# Build Next.js production bundle
```
**Why separate stage?**
- Build artifacts needed for production
- Removes build tools from final image
- Results in smaller image size

### Stage 2: Build Backend Dependencies
```dockerfile
FROM python:3.11-slim AS backend-builder
# Install Python packages
```
**Why separate stage?**
- Compilation tools (gcc, g++) only needed for building
- Don't include in final image
- Keeps final image clean and small

### Stage 3: Final Production Image
```dockerfile
FROM python:3.11-slim
# Copy compiled artifacts from builders
# Install only runtime dependencies
# Use supervisor to run both services
```

**Size comparison:**
- Without multi-stage: ~1.5 GB
- With multi-stage: ~800 MB
- **Savings**: ~50% smaller image

## Supervisor: Running Multiple Processes

**Problem**: Docker containers typically run one process.
**Solution**: Supervisor manages multiple processes in one container.

**Configuration**: `/docker/supervisord.conf`

```ini
[program:backend]
command=uvicorn main:app --host 0.0.0.0 --port 8000

[program:frontend]
command=node server.js
```

**How it works:**
1. Container starts
2. Entrypoint script runs initialization
3. Supervisor starts both backend and frontend
4. Both processes run simultaneously
5. If one crashes, Supervisor restarts it automatically

## Security Best Practices

### Non-Root User

```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

**Why:**
- Containers shouldn't run as root
- Limits damage if container compromised
- Best practice for production

### Health Checks

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:3000 && curl -f http://localhost:8000/health
```

**What it does:**
- Checks every 30 seconds if services are responding
- Docker marks container unhealthy if checks fail
- Orchestrators (Docker Swarm, Kubernetes) can auto-restart

**For users:**
```bash
# Check health status
docker inspect channelfinwatcher | grep Health -A 10
```

## Troubleshooting CI/CD

### Build Fails in GitHub Actions

**Check the logs:**
1. Go to Actions tab in GitHub
2. Click the failed workflow
3. Expand failed steps

**Common issues:**

**Dockerfile syntax error:**
```
ERROR: failed to solve: failed to parse Dockerfile
```
**Fix**: Check Dockerfile for syntax errors

**Build dependency missing:**
```
ERROR: Could not find a version that satisfies the requirement
```
**Fix**: Update requirements.txt or package.json

**Out of disk space:**
```
ERROR: no space left on device
```
**Fix**: Usually temporary, retry the workflow

### Image Not Updating

**Problem**: Pulled new image but still using old version

**Solution 1: Force recreation**
```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate
```

**Solution 2: Remove old container**
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

**Solution 3: Check image digest**
```bash
# On GHCR (from Actions logs)
Image digest: sha256:abc123...

# Locally
docker images --digests | grep channelfinwatcher
```

### Can't Access Published Image

**Problem**: `docker pull ghcr.io/miguelarios/channelfinwatcher:latest` fails

**Check visibility:**
1. Go to your repository on GitHub
2. Click "Packages" on right side
3. Click on channelfinwatcher package
4. Check visibility setting (should be Public)

**Make package public:**
1. Go to package settings
2. Scroll to "Danger Zone"
3. Click "Change visibility"
4. Select "Public"

## Advanced: Manual Docker Build

If you need to build locally without GitHub Actions:

```bash
# Build for your architecture only
docker build -t channelfinwatcher:local .

# Build for multiple architectures (requires buildx)
docker buildx create --use
docker buildx build --platform linux/amd64,linux/arm64 \
    -t ghcr.io/miguelarios/channelfinwatcher:manual \
    --push .
```

## Next Steps

1. **First push to main** will trigger your first automated build
2. **Watch the Actions tab** to see the build progress
3. **Check the Packages** section to see your published image
4. **Test deployment** using docker-compose.prod.yml

## Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GHCR Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Multi-stage Builds](https://docs.docker.com/build/building/multi-stage/)
- [Supervisor Documentation](http://supervisord.org/)
