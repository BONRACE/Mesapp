# Salubre Cité — Plateforme Multi-Rôles de Gestion des Déchets, PostGIS & Bourse Circulaire

## Architecture du Dossier
- `frontend/` : Application React 18 + Vite + Tailwind CSS v4 (Accueil, Auth OTP 6 chiffres, Poste de pilotage GPS PostGIS, Studio QR signé HMAC-SHA256, Bourse des matières recyclées avec passerelles FedaPay / KkiaPay / Stripe, et explorateur de code Backend).
- `backend/` : API Python **FastAPI** + **SQLAlchemy 2.0 Async** + **GeoAlchemy2 (PostgreSQL / PostGIS SRID 4326)** (`models.py`, `schemas.py`, `database.py`, `main.py`).
- `docker-compose.yml` : Lance PostgreSQL 16 + PostGIS 3.4 et l'API FastAPI.

## Démarrage rapide
### 1. Frontend (interface complète interactive)
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

### 2. Backend FastAPI + PostGIS
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000   # Documentation Swagger sur http://localhost:8000/docs
```
