# Installation Guide — Migration Intelligence Platform

## 📋 Prerequisites

- **Python:** 3.9 or higher
- **Node.js:** 16.0 or higher
- **npm:** 8.0 or higher
- **Git:** Latest version

Verify installations:

```bash
python --version
node --version
npm --version
```

---

## ⚡ Quick Start (Recommended)

### Option 1: Automatic Setup (Windows Batch)

```bash
setup.bat
```

This runs:

1. ✅ Frontend npm install
2. ✅ Backend pip install
3. ✅ Environment configuration

---

### Option 2: Manual Setup (Cross-Platform)

#### Step 1: Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 2: Install Backend Dependencies

```bash
cd backend

# Standard installation (recommended)
pip install -r requirements.txt

# Development installation (with testing tools)
pip install -r ../requirements-dev.txt

# Production installation (for deployment)
pip install -r ../requirements-prod.txt
```

#### Step 3: Verify Installation

```bash
pip list
python -m fastapi --version
```

#### Step 4: Install Frontend Dependencies

```bash
cd ../frontend
npm install
```

#### Step 5: Environment Setup

```bash
cd ..
npm run setup
```

---

## 📦 Requirements Files Explained

| File                    | Purpose                         | Use Case                           |
| ----------------------- | ------------------------------- | ---------------------------------- |
| `requirements.txt`      | **Core dependencies**           | Production & fresh installs        |
| `requirements-dev.txt`  | Core + testing/dev tools        | Local development                  |
| `requirements-prod.txt` | Core + production optimizations | Cloud deployment (Railway, Heroku) |

---

## 🚀 Running the Application

### Frontend (Terminal 1)

```bash
cd frontend
npm run dev
```

→ Open http://localhost:3000

### Backend (Terminal 2)

```bash
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

→ API: http://localhost:8000/docs

### Alternative: Production Build

```bash
# Frontend production
cd frontend
npm run build
npm start

# Backend production
cd backend
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

---

## 🔧 Troubleshooting Installation

### Error: `pip: command not found`

**Solution:** Use `python -m pip` instead:

```bash
python -m pip install -r requirements.txt
```

### Error: `ModuleNotFoundError: No module named 'fastapi'`

**Solution:** Ensure virtual environment is activated:

```bash
# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

### Error: `npm ERR! 404 Not Found`

**Solution:** Clear npm cache and reinstall:

```bash
npm cache clean --force
npm install
```

### Error: `Execution Policies` (Windows PowerShell)

**Solution:** Allow script execution:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then retry setup.bat

### Error: Python version incompatible

**Solution:** Check your Python version:

```bash
python --version  # Should be 3.9+
```

Install Python 3.11 or higher if needed.

### Error: `hnswlib` wheel failed to build on Windows

**Cause:** On Windows, `hnswlib` may not have a prebuilt binary wheel for newer Python versions such as 3.14, so pip falls back to source compilation.

**Solution:**

1. Install Microsoft Visual C++ Build Tools:

```powershell
winget install --id Microsoft.VisualStudio.2022.BuildTools
```

2. Upgrade pip build tools and retry:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

3. If you only need a stable install path on Windows, use Python 3.11 or 3.12 instead of Python 3.14.

---

## 📊 Dependency Breakdown

### Core Stack

- **FastAPI 0.104.1** — Web framework
- **Next.js 16.2.2** — React frontend
- **SQLAlchemy 2.0.23** — ORM
- **Pydantic 2.5.0** — Data validation

### ML/AI Stack

- **scikit-learn 1.3.2** — Machine learning
- **XGBoost 2.0.3** — Gradient boosting
- **Prophet 1.1.4** — Time series forecasting
- **SHAP 0.43.0** — Model explainability
- **google-genai 0.3.0** — Gemini LLM

### RAG Stack

- **Chromadb 0.4.22** — Vector database
- **sentence-transformers 2.2.2** — Embeddings
- **hnswlib 0.7.0** — Vector indexing

---

## ✅ Verification Checklist

After installation, verify everything works:

- [ ] Python virtual environment activated
- [ ] `pip list` shows all packages
- [ ] `python -c "import fastapi; print(fastapi.__version__)"` works
- [ ] `npm list` shows all frontend packages
- [ ] Backend starts without errors: `python -m uvicorn main:app --reload`
- [ ] Frontend builds: `cd frontend && npm run build`
- [ ] `.env` file exists and has required variables

---

## 🔄 Updating Dependencies

### Update All Packages

```bash
# Upgrade pip, setuptools, wheel
python -m pip install --upgrade pip setuptools wheel

# Update all packages to latest compatible versions
pip install --upgrade -r requirements.txt
```

### Update Specific Package

```bash
pip install --upgrade chromadb
pip install --upgrade fastapi
```

---

## 📝 Environment Variables (.env)

Create `.env` file in root directory:

```env
# Backend
DATABASE_URL=sqlite:///./data/processed/warehouse.db
REDIS_URL=redis://localhost:6379/0
GEMINI_API_KEY=your_gemini_key_here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

# General
DEBUG=true
```

---

## 🐳 Docker Installation (Optional)

```bash
# Build and run with Docker Compose
docker-compose up --build

# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

---

## 📞 Support

For issues, check:

1. Python 3.9+ installed
2. Virtual environment activated
3. All core dependencies in `requirements.txt` installed
4. `.env` file configured
5. Logs in backend terminal
