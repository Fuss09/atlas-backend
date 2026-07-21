# ─── Stage 1: Builder ────────────────────────────────────────────────────────
# Installe les dépendances dans un environnement isolé
FROM python:3.12-slim AS builder

WORKDIR /app

# Dépendances système minimales pour la compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copier uniquement pyproject.toml d'abord (cache Docker)
COPY pyproject.toml .

# Créer le virtualenv et installer les dépendances
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -e ".[dev]"


# ─── Stage 2: Runtime ─────────────────────────────────────────────────────────
# Image finale légère — sans les outils de build
FROM python:3.12-slim AS runtime

WORKDIR /app

# Dépendances runtime uniquement
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier le venv depuis le builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Utilisateur non-root pour la sécurité
RUN groupadd -r atlas && useradd -r -g atlas atlas

# Cache des libs externes (yfinance/platformdirs) : l'utilisateur atlas n'a pas
# de home inscriptible. On redirige XDG_CACHE_HOME vers /tmp (toujours
# accessible en écriture) — sinon yfinance échoue à créer son cache, ce qui le
# ralentit fortement et l'expose au rate-limit sur les gros runs.
ENV XDG_CACHE_HOME=/tmp/atlas-cache

USER atlas

# Copier le code source
COPY --chown=atlas:atlas . .

# Variables d'environnement par défaut (overridées par docker-compose)
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Port exposé
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
