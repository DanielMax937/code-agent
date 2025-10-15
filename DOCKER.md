# Docker Deployment Guide

This guide explains how to run the Code Agent using Docker.

## Prerequisites

- Docker installed (version 20.10 or higher)
- Docker Compose installed (version 1.29 or higher)
- Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

## What's Included in the Docker Image

The Docker image includes:

- ✅ Python 3.11
- ✅ Git (for version control in workflows)
- ✅ Node.js 20 (for JavaScript/TypeScript testing)
- ✅ npm & npx (for running test frameworks)
- ✅ gemini-cli (Google Generative AI CLI)
- ✅ All Python dependencies from `requirements.txt`

## Quick Start

### 1. Set Your API Key

Create a `.env` file in the project root:

```bash
# Copy the example file
cp .env.example .env

# Edit and add your Gemini API key
nano .env
```

Add your key:
```
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 2. Build and Run with Docker Compose

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the container
docker-compose down
```

The application will be available at: `http://localhost:8000`

### 3. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:8000
```

## Manual Docker Commands

If you prefer to use Docker directly without Compose:

### Build the Image

```bash
docker build -t code-agent:latest .
```

### Run the Container

```bash
docker run -d \
  --name code-agent \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_gemini_api_key \
  -v $(pwd)/temp:/app/temp \
  code-agent:latest
```

### View Logs

```bash
docker logs -f code-agent
```

### Stop and Remove

```bash
docker stop code-agent
docker rm code-agent
```

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GEMINI_API_KEY` | Your Gemini API key | Yes | - |
| `PYTHONUNBUFFERED` | Python output buffering | No | 1 |
| `HOST` | Server host | No | 0.0.0.0 |
| `PORT` | Server port | No | 8000 |

## Volume Mounts

The container uses the following volumes:

- `./temp:/app/temp` - Temporary files for code analysis and modifications
- `./templates:/app/templates` - HTML templates (for development)

## Health Check

The container includes a health check that runs every 30 seconds:

```bash
# Check container health
docker ps

# Manual health check
curl http://localhost:8000/health
```

## Development Mode

To run with live code reloading during development:

```bash
docker run -d \
  --name code-agent-dev \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_key \
  -v $(pwd):/app \
  code-agent:latest \
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Troubleshooting

### Container won't start

1. Check if port 8000 is already in use:
   ```bash
   lsof -i :8000
   ```

2. Check Docker logs:
   ```bash
   docker-compose logs code-agent
   ```

### Gemini CLI not working

1. Verify API key is set:
   ```bash
   docker exec code-agent env | grep GEMINI
   ```

2. Test gemini-cli inside container:
   ```bash
   docker exec -it code-agent gemini --version
   ```

### Git operations failing

1. Verify git is installed:
   ```bash
   docker exec -it code-agent git --version
   ```

2. Check git configuration:
   ```bash
   docker exec -it code-agent git config --list
   ```

## Production Deployment

For production deployment, consider:

1. **Use environment variable files**:
   ```bash
   docker-compose --env-file .env.production up -d
   ```

2. **Add reverse proxy** (nginx/traefik) for HTTPS

3. **Set resource limits**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 2G
   ```

4. **Use Docker secrets** for sensitive data:
   ```yaml
   secrets:
     - gemini_api_key
   ```

5. **Enable logging driver**:
   ```yaml
   logging:
     driver: "json-file"
     options:
       max-size: "10m"
       max-file: "3"
   ```

## Multi-Stage Build (Advanced)

For smaller production images, the Dockerfile uses a multi-stage approach:

1. **Build stage**: Compiles dependencies
2. **Runtime stage**: Only includes necessary runtime files

This reduces the final image size significantly.

## Security Considerations

1. **Never commit `.env` files** with real API keys
2. **Use Docker secrets** in production
3. **Run as non-root user** (add to Dockerfile):
   ```dockerfile
   RUN useradd -m -u 1000 appuser
   USER appuser
   ```
4. **Scan images regularly**:
   ```bash
   docker scan code-agent:latest
   ```

## Support

For issues or questions:
- Check the main README.md
- Review Docker logs
- Open an issue on GitHub

