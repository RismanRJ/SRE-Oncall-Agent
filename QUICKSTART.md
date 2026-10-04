# Quick Start - Local Development

## 🚀 Run in 3 Commands

### 1. Navigate to project
```bash
cd <project-dir>
```

### 2. Start Docker (with hot-reload)
```bash
docker-compose -f docker-compose.dev.yaml up --build
```

### 3. Open in browser
```
http://localhost:8501
```

---

## 📝 Login Credentials

**Admin Account:**
- Email: `admin@example.com`
- Password: `change-me-admin`

**Engineer Account:**
- Email: `bob@example.com`
- Password: `change-me-bob`

---

## ✨ Features to Try

### As Admin:
1. ✓ Login with admin credentials
2. ✓ Go to "Admin" tab → "📅 Add/Edit Rotation"
3. ✓ Pick **Start Date** → **End Date** → Select **Engineer**
4. ✓ Click "➕ Add Rotation"
5. ✓ View in "📋 View Rotations" tab
6. ✓ See next 7 days schedule

### As Engineer:
1. ✓ Login with engineer credentials
2. ✓ See current on-call engineer on Home tab
3. ✓ View all incidents in "Incidents" tab

### Test an Incident:
```bash
# In another terminal, get a JWT token:
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"bob@example.com","password":"change-me-bob"}' | jq -r '.token')

# Trigger incident:
curl -X POST http://localhost:8000/webhook/check \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"checkout-service","metrics":{"tp99_ms":3500}}'

# Refresh Streamlit → See incident appear!
```

---

## 🔄 Auto-Reload Works!

Edit any file and it will auto-reload:

```bash
# Example: Edit auth/users.py
vi auth/users.py

# Add a new user, save (Cmd+S)
# → Container auto-reloads
# → Try logging in with new credentials
```

---

## 🛑 Stop Container

```bash
# Press Ctrl+C in the terminal, or:
docker-compose -f docker-compose.dev.yaml down
```

---

## 📚 More Info

Full development guide: `DOCKER_DEV.md`

---

## 🎯 What's Next?

After testing locally:
- **Phase 6**: Add New Relic integration
- **Phase 12**: Add notifications (Slack + SMS + IVR)
- **Deploy**: Use production `docker-compose.yaml`

