# Docker Local Development Setup

## Quick Start

### Prerequisites
- Docker installed (`docker --version`)
- Docker Compose installed (`docker-compose --version`)

### 1. Start Docker Dev Container

```bash
cd <project-dir>
docker-compose -f docker-compose.dev.yaml up --build
```

**What happens:**
- ✓ Builds Docker image from Dockerfile
- ✓ Mounts all source code as volumes (live code reload)
- ✓ Sets `DEV_MODE=true` for FastAPI auto-reload
- ✓ Starts both FastAPI (port 8000) and Streamlit (port 8501)
- ✓ Auto-reloads on any code change in your editor

### 2. Access the Application

| Service | URL | Purpose |
|---------|-----|---------|
| **Streamlit Dashboard** | http://localhost:8501 | Main UI (login here) |
| **FastAPI Docs** | http://localhost:8000/docs | API documentation |
| **Health Check** | http://localhost:8000/health | Server status |

### 3. Demo Login Credentials

```
Admin:
  Email: admin@example.com
  Password: change-me-admin

Engineer:
  Email: bob@example.com
  Password: change-me-bob
```

---

## Development Workflow

### Edit Code & See Changes Live

1. **Open your editor** (VS Code, etc.)
2. **Edit any Python file** in `<project-dir>/`
3. **Save the file** (Cmd+S)
4. **FastAPI reloads** automatically (check console logs)
5. **Refresh dashboard** in browser to see Streamlit changes

### Example: Add a new on-call engineer

```bash
# 1. Edit auth/users.py
vi auth/users.py

# 2. Add new user:
# "newengineer@company.com": {
#   "password": "pass123",
#   "name": "New Engineer",
#   "role": "engineer",
#   "phone": "+1-555-0105",
#   "slack_id": "UNEWENG"
# }

# 3. Save file (Cmd+S)
# 4. Watch console for "Reloading modules..."
# 5. Refresh Streamlit and try logging in
```

---

## Useful Commands

### View logs
```bash
# Follow logs in real-time
docker-compose -f docker-compose.dev.yaml logs -f

# Just FastAPI logs
docker-compose -f docker-compose.dev.yaml logs -f sre-agent | grep "fastapi"

# Just Streamlit logs
docker-compose -f docker-compose.dev.yaml logs -f sre-agent | grep "streamlit"
```

### Stop container
```bash
docker-compose -f docker-compose.dev.yaml down
```

### Restart container
```bash
docker-compose -f docker-compose.dev.yaml restart
```

### Remove container & rebuild
```bash
docker-compose -f docker-compose.dev.yaml down --rmi all
docker-compose -f docker-compose.dev.yaml up --build
```

### Shell into container
```bash
docker-compose -f docker-compose.dev.yaml exec sre-agent bash
```

---

## Docker Volume Mounts (Live Reload)

These directories are **live-mounted** so changes reflect immediately:

```
<project-dir>/  →  /app/ (inside container)
├── server.py                                  → Changes detected instantly
├── app.py
├── agent/
├── auth/
├── oncall/
├── thresholds/
├── tools/
├── notifications/
├── configs/
└── storage/                                   → Incidents persist to host
```

**Any edit to these files → auto-reload in container**

---

## Troubleshooting

### Port already in use
```bash
# Kill any existing process on port 8000/8501
lsof -i :8000
lsof -i :8501
kill -9 <PID>

# Then try again
docker-compose -f docker-compose.dev.yaml up
```

### Container crashes on startup
```bash
# Check logs
docker-compose -f docker-compose.dev.yaml logs

# Common issues:
# - Missing .env.dev file
# - Python import errors (check logs)
# - Port already in use
```

### Changes not reflecting
```bash
# 1. Check if file was saved
# 2. Check logs for reload message
# 3. Restart container
docker-compose -f docker-compose.dev.yaml restart

# 4. If still not working, rebuild
docker-compose -f docker-compose.dev.yaml down
docker-compose -f docker-compose.dev.yaml up --build
```

### Ollama not accessible from Docker
```bash
# Update .env.dev:
OLLAMA_HOST=http://host.docker.internal:11434  # Mac/Windows
# or
OLLAMA_HOST=http://172.17.0.1:11434           # Linux
```

---

## Production vs Development

| Aspect | Dev | Production |
|--------|-----|-------------|
| **Auto-reload** | ✓ Yes | ✗ No |
| **Volume mounts** | ✓ Yes (live code) | ✗ No |
| **Image** | Rebuilt each time | Cached, optimized |
| **Error logging** | Verbose | Production-only |
| **Compose file** | `docker-compose.dev.yaml` | `docker-compose.yaml` |

**To run production version:**
```bash
docker-compose up --build
```

---

## Development Tips

### Create test incidents quickly
```bash
# Login to get token, then:
TOKEN="<jwt_token>"

curl -X POST http://localhost:8000/webhook/check \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"checkout-service","metrics":{"tp99_ms":3500}}'
```

### Test admin functionality
```bash
# Login as admin (admin@example.com)
# → Go to "Admin" tab in sidebar
# → Add new on-call rotation with date picker
# → Verify it appears in "View Rotations" tab
```

### Check incident storage
```bash
# View stored incidents
ls -la storage/incidents/

# Check latest incident
cat storage/incidents/*/INC*.json | jq . | tail -20
```

---

## Performance Tips

- **Streamlit caching**: Use `@st.cache_data` for expensive operations
- **API caching**: Add caching headers in FastAPI endpoints
- **Volume mounts**: Only essential files mounted (see `.dockerignore`)

---

## Next Steps

After local dev is working:

1. **Phase 6**: Integrate real New Relic metrics
2. **Phase 12**: Build notification dispatcher
3. **Production deployment**: Push to AWS/Lightsail using production compose file

