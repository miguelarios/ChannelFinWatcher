# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a software project with complete requirements and user stories documented in @docs/prd.md and technical architecture and implementation details in @docs/tdd.md. Reference these documents for all project-specific information, requirements, and technical decisions.

## Development Workflow & Preferences

### Extended Thinking
For complex problems, I may ask you to think deeper:
- "think" - standard analysis
- "think hard" - more thorough consideration
- "think harder" - deep architectural analysis
- "ultrathink" - maximum reasoning for critical decisions

### Educational Development Approach
When working on this project, always explain the "why" behind technical decisions:

#### Explain Technical Choices
- **Why we chose this technology stack** (FastAPI + NextJS + Docker)
- **Why we structure code this way** (separation of concerns, testability)
- **Why we use specific patterns** (dependency injection, health checks, migrations)
- **Why we configure things certain ways** (environment variables, mount points)

#### Teaching Moments
- **Before implementing**: Explain what we're about to build and why
- **During implementation**: Call out key patterns and best practices
- **After testing**: Explain what the tests validate and why it matters
- **When debugging**: Show thought process for diagnosing issues

#### Architecture Explanations
- **Database design decisions**: Why these tables, relationships, indexes
- **API design patterns**: Why REST + WebSocket, how endpoints relate
- **Docker strategies**: Why multi-service, volume mounts vs named volumes
- **Configuration management**: Why YAML + database hybrid approach

#### Code Quality Teaching
- **Show alternative approaches**: "We could do X, but Y is better because..."
- **Explain trade-offs**: Performance vs simplicity, flexibility vs constraints
- **Point out common pitfalls**: Things that often go wrong and how to avoid them
- **Highlight debugging techniques**: How to trace issues, useful commands

#### Real-world Context
- **Connect to larger patterns**: How this relates to microservices, 12-factor apps
- **Production considerations**: What would change for larger scale deployment
- **Maintenance implications**: How these choices affect long-term maintenance

The goal is to make each development session a learning opportunity, not just completing tasks.

## Development Commands

For project-specific development commands, tooling, and workflows, see @docs/development-guide.md.

For testing framework usage and patterns, see @docs/testing-guide.md.

For code documentation standards, see @docs/code-documentation-guide.md.

## Docker Development Commands

For consistent testing environment across different machines:

```bash
# Start development server with Docker
docker compose -f docker-compose.dev.yml up

# Start with rebuild (after dependency changes)
docker compose -f docker-compose.dev.yml up --build

# Run in background (detached mode)
docker compose -f docker-compose.dev.yml up -d

# Stop and clean up containers
docker compose -f docker-compose.dev.yml down

# View logs
docker compose -f docker-compose.dev.yml logs -f
```

## Git Workflow

### Daily Workflow
Every time you make meaningful changes (aim for commits every 30-60 minutes):
```bash
# What changed?
git status

# Review the actual changes before committing (great learning moment!)
git diff

# Stage all changes (or use git add <specific-files> for selective staging)
git add .

# Commit with descriptive message
git commit -m "feat: implement quick split calculator"

# Push to GitHub for backup and collaboration
git push
```

### Example Commit Messages
```bash
git commit -m "feat: implement quick split calculator"
git commit -m "fix: handle zero tabs edge case"
git commit -m "style: improve mobile responsiveness"
git commit -m "refactor: extract calculation logic to utils"
git commit -m "docs: add JSDoc comments to QuickSplit component"
```

### Commit Message Format
- `feat:` - new features
- `fix:` - bug fixes
- `refactor:` - code improvements
- `style:` - UI/styling changes
- `docs:` - documentation updates
- `test:` - test additions/changes

### Story Completion
After each user story is fully implemented and tested:
```bash
# Create a tag for the milestone
git tag -a v0.1-story-1 -m "Complete Story 1: Quick even split"

# Push changes and tags
git push origin main --tags
```

### GitHub CLI Integration
```bash
# Create issue for next story
gh issue create --title "Story 2: Photo OCR" --body "Implement receipt photo capture and OCR"

# Create PR for review
gh pr create --title "feat: add quick split functionality" --body "Implements Story 1"

# Check workflow status
gh workflow view
```

### Branching Strategy
```bash
# Create feature branch for each story
git checkout -b feature/story-1-quick-split

# After completion and review
git checkout main
git merge feature/story-1-quick-split
```