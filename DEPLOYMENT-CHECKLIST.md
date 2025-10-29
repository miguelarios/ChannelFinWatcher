# Deployment Setup Checklist

Quick checklist to get your ChannelFinWatcher project ready for production deployment.

## ✅ What We've Set Up

### 1. Directory Structure Consolidation
- ✅ Merged `/config` into `/data` directory
- ✅ Updated all paths to use `/app/data/config.yaml`
- ✅ Updated cookies.txt path to `/app/data/cookies.txt`
- ✅ Simplified to 3 directories: `data/`, `media/`, `temp/`

### 2. Production Dockerfiles
- ✅ Created `/Dockerfile` - Root-level multi-stage build
- ✅ Created `/backend/Dockerfile.prod` - Production backend
- ✅ Created `/frontend/Dockerfile.prod` - Production frontend
- ✅ Configured supervisor for multi-process management
- ✅ Added health checks for both services
- ✅ Created entrypoint script for initialization

### 3. Docker Configuration Files
- ✅ Created `/docker/supervisord.conf` - Process manager config
- ✅ Created `/docker/entrypoint.sh` - Container initialization script

### 4. GitHub Actions CI/CD
- ✅ Created `.github/workflows/docker-publish.yml`
- ✅ Configured automatic builds on push to main
- ✅ Configured version tagging on git tags
- ✅ Set up GitHub Container Registry (GHCR) publishing
- ✅ Enabled multi-architecture builds (AMD64 + ARM64)

### 5. Production Deployment Files
- ✅ Updated `docker-compose.prod.yml` - User-facing deployment file
- ✅ Simplified to single service pulling pre-built image

### 6. Documentation
- ✅ Created `/docs/DEPLOYMENT.md` - Comprehensive deployment guide
- ✅ Created `/docs/CI-CD-EXPLAINED.md` - CI/CD system explanation
- ✅ Updated `README.md` with deployment instructions

### 7. Configuration Updates
- ✅ Updated `backend/app/config.py` - Consolidated paths
- ✅ Updated `docker-compose.dev.yml` - Removed /config mount
- ✅ Updated `.gitignore` - Simplified exclusions
- ✅ Updated `frontend/next.config.js` - Added standalone output mode

## 🚀 Next Steps to Deploy

### Step 1: Test Locally (Optional but Recommended)

Test the production build locally before pushing:

```bash
# Build the production image locally
docker build -t channelfinwatcher:test .

# Test run with docker-compose (modify image name temporarily)
# Edit docker-compose.prod.yml to use: image: channelfinwatcher:test
docker compose -f docker-compose.prod.yml up

# Access at http://localhost:3000 and verify everything works
```

### Step 2: Commit and Push Changes

```bash
# Stage all new files
git add .

# Commit with descriptive message
git commit -m "feat: add production deployment with GitHub Actions CI/CD

- Consolidate config into /data directory
- Add multi-stage Dockerfile for production
- Configure GitHub Actions for automated builds
- Add comprehensive deployment documentation
- Set up GitHub Container Registry publishing
"

# Push to GitHub
git push origin main
```

### Step 3: Monitor First Build

1. **Go to GitHub**: Visit your repository
2. **Click "Actions" tab**: See your workflow running
3. **Watch the build**: Takes ~10-15 minutes for first build
4. **Check for success**: Wait for green checkmark ✅

**Expected timeline:**
- Checkout & setup: ~30 seconds
- Build backend stage: ~3-5 minutes
- Build frontend stage: ~2-4 minutes
- Multi-platform builds: ~3-5 minutes
- Push to GHCR: ~1-2 minutes

### Step 4: Verify Package Published

1. **Go to your GitHub profile** or repository
2. **Click "Packages" section** (right sidebar)
3. **Find channelfinwatcher package**
4. **Check visibility**: Should be "Public"

If not public:
- Click on package → Settings → Change visibility → Public

### Step 5: Test User Deployment

On a clean machine (or clean directory), test the user experience:

```bash
# Simulate end-user deployment
mkdir -p ~/test-deploy/channelfinwatcher/{data,media,temp}
cd ~/test-deploy/channelfinwatcher

# Download production compose file
curl -O https://raw.githubusercontent.com/miguelarios/ChannelFinWatcher/main/docker-compose.prod.yml

# Pull and start (as end-user would)
docker compose -f docker-compose.prod.yml up -d

# Check logs
docker compose -f docker-compose.prod.yml logs -f

# Access UI
open http://localhost:3000

# Test adding a channel and triggering download

# Clean up test
docker compose -f docker-compose.prod.yml down
cd ~ && rm -rf ~/test-deploy
```

### Step 6: Create First Release (Optional)

Once you verify everything works:

```bash
# Tag a version
git tag -a v1.0.0 -m "First production release

- Core channel management
- Automated downloads with scheduler
- YouTube Shorts filtering
- Automatic video cleanup
- Web UI for monitoring
"

# Push the tag
git push origin v1.0.0
```

This triggers another build with version tags: `1.0.0`, `1.0`, and `latest`

## 📋 Pre-Deployment Checklist

Before your first deployment, verify:

- [ ] GitHub repository is public (or Actions enabled for private)
- [ ] GitHub Actions is enabled (Settings → Actions → Allow all actions)
- [ ] GHCR package will be public (or document authentication)
- [ ] All tests pass locally: `docker compose -f docker-compose.dev.yml up`
- [ ] README has correct repository URLs
- [ ] Documentation links are correct
- [ ] `.env` and secrets are not committed (check `.gitignore`)

## 🐛 Troubleshooting First Deployment

### Build Fails in GitHub Actions

**Check the Actions tab:**
```
Actions → Click failed workflow → Expand failed step
```

**Common first-time issues:**

1. **Dockerfile syntax error**
   - Review Dockerfile for typos
   - Test locally: `docker build -t test .`

2. **Missing dependencies**
   - Check requirements.txt (backend)
   - Check package.json (frontend)

3. **Permission issues**
   - Usually auto-resolved by GitHub Actions
   - Verify GITHUB_TOKEN has package write permissions

4. **Timeout**
   - First build takes longer (no cache)
   - Retry the workflow (it will be faster with cache)

### Can't Pull Published Image

**Error:** `Error response from daemon: manifest not found`

**Solutions:**
1. Verify image exists: Check GitHub Packages section
2. Check image name exactly matches: `ghcr.io/yourusername/repo:latest`
3. Make package public: Package Settings → Change visibility
4. Wait a moment: GHCR can take 1-2 minutes to propagate

### Container Starts but Services Don't Work

**Check logs:**
```bash
docker compose -f docker-compose.prod.yml logs
```

**Look for:**
- Backend startup errors
- Frontend build issues
- Database initialization problems
- Missing directories

**Common fixes:**
```bash
# Ensure directories exist
mkdir -p data media temp

# Check permissions
ls -la data/ media/ temp/

# Recreate container
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

## 📚 Documentation Quick Links

- **For End Users**: [DEPLOYMENT.md](docs/DEPLOYMENT.md)
- **Understanding CI/CD**: [CI-CD-EXPLAINED.md](docs/CI-CD-EXPLAINED.md)
- **Development**: [CLAUDE.md](CLAUDE.md)
- **Quick Start**: [README.md](README.md)

## 🎯 Success Criteria

Your deployment is successful when:

1. ✅ GitHub Actions builds complete successfully
2. ✅ Image appears in GitHub Packages (public)
3. ✅ You can pull: `docker pull ghcr.io/miguelarios/channelfinwatcher:latest`
4. ✅ You can start with docker-compose.prod.yml
5. ✅ Web UI accessible at http://localhost:3000
6. ✅ Can add channels and trigger downloads
7. ✅ Videos appear in media directory

## 🎉 After Successful Deployment

Update your README with:
- Link to published package
- Badge showing build status
- Clear deployment instructions

Example badge:
```markdown
![Docker Build](https://github.com/miguelarios/ChannelFinWatcher/actions/workflows/docker-publish.yml/badge.svg)
```

Share with users:
```markdown
## Quick Deploy

docker run -d \
  -p 3000:3000 \
  -v ./data:/app/data \
  -v ./media:/app/media \
  -v ./temp:/app/temp \
  ghcr.io/miguelarios/channelfinwatcher:latest
```

## Need Help?

If you encounter issues:

1. **Check logs first**:
   ```bash
   docker compose -f docker-compose.prod.yml logs
   ```

2. **Review documentation**:
   - [DEPLOYMENT.md](docs/DEPLOYMENT.md) for deployment issues
   - [CI-CD-EXPLAINED.md](docs/CI-CD-EXPLAINED.md) for build issues

3. **GitHub Actions logs**:
   - Actions tab → Click workflow → View logs

4. **Test locally first**:
   ```bash
   docker build -t test .
   docker run -p 3000:3000 -p 8000:8000 test
   ```

Good luck with your deployment! 🚀
