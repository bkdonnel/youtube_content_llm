# Docker Guide

## Quick Start

### 1. Build the Docker Image

```bash
docker-compose build
```

### 2. Run Different Services

#### Test with Single Zen World Video
```bash
docker-compose --profile test up test
```

#### Download from All Creators (One-Time)
```bash
docker-compose --profile download up download
```

#### Run Automated Pipeline (Continuous Monitoring)
```bash
docker-compose --profile pipeline up -d pipeline
```

#### Run Search API Only
```bash
docker-compose --profile api up -d api
```
Then visit: http://localhost:8000

#### Run Full Stack (Pipeline + API)
```bash
docker-compose up -d
```

### 3. View Logs

```bash
# View pipeline logs
docker-compose logs -f pipeline

# View API logs
docker-compose logs -f api
```

### 4. Stop Services

```bash
# Stop all services
docker-compose down

# Stop specific service
docker-compose --profile pipeline down
```

## File Structure

- **music_tutorials/** - Downloaded audio, transcripts, and metadata (mounted as volume)
- **database/** - SQLite database for tracking processed videos (mounted as volume)
- **.env** - Environment variables (API keys, configuration)

## Environment Variables

Make sure your `.env` file contains:
```
OPENAI_API_KEY=your-key-here
MILVUS_URI=your-milvus-uri
MILVUS_TOKEN=your-milvus-token
OUTPUT_DIR=music_tutorials
CHECK_INTERVAL_MINUTES=60
MAX_VIDEOS_PER_CHECK=5
```

## Common Commands

```bash
# Rebuild after code changes
docker-compose build

# Run test and remove container after
docker-compose --profile test run --rm test

# Shell into running container
docker-compose exec pipeline bash

# View all running containers
docker-compose ps

# Remove all stopped containers and volumes
docker-compose down -v
```

## Production Deployment

For production, consider:
1. Using Docker Swarm or Kubernetes for orchestration
2. Setting up health checks
3. Configuring log rotation
4. Using secrets management instead of .env files
5. Setting up automated backups of the database and transcripts
