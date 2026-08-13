# Deployment Guide

## RIBDIGI BUSINESS ERP — MVP Deployment Documentation

**Version:** 1.0.0  
**Classification:** Internal — DevOps & Engineering  
**Last Updated:** August 2026  
**Applies To:** RIBDIGI ERP MVP (Version 1.0)

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [Local Development Environment](#3-local-development-environment)
4. [Docker Deployment](#4-docker-deployment)
5. [Kubernetes Deployment](#5-kubernetes-deployment)
6. [CI/CD Pipeline](#6-cicd-pipeline)
7. [Database Migration Strategy](#7-database-migration-strategy)
8. [Environment Configuration](#8-environment-configuration)
9. [Monitoring & Observability](#9-monitoring--observability)
10. [Scaling & High Availability](#10-scaling--high-availability)
11. [Backup & Disaster Recovery](#11-backup--disaster-recovery)
12. [Security Hardening](#12-security-hardening)
13. [Troubleshooting](#13-troubleshooting)
14. [Appendix: Resource Requirements](#appendix-resource-requirements)

---

## 1. Overview

This guide provides comprehensive instructions for deploying the RIBDIGI BUSINESS ERP MVP across environments: local development, staging, and production. The platform is containerized with Docker and orchestrated via Kubernetes, with CI/CD automation through GitHub Actions.

**Deployment Targets:**
- **Local:** Docker Compose for development
- **Staging:** Kubernetes cluster (cloud or on-premise)
- **Production:** Managed Kubernetes (EKS, GKE, or AKS)

**Architecture Summary:**
```
┌─────────────────────────────────────────────────────────────┐
│                        Ingress / Load Balancer               │
│                    TLS Termination, Rate Limiting            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Kubernetes Cluster                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Frontend   │  │   Backend   │  │  Celery Workers     │ │
│  │  (Next.js)  │  │  (FastAPI)  │  │  (Background Jobs)  │ │
│  │  Replica: 3 │  │  Replica: 5 │  │  Replica: 3         │ │
│  └─────────────┘  └──────┬──────┘  └─────────────────────┘ │
│                          │                                  │
│  ┌─────────────┐  ┌──────▼──────┐  ┌─────────────────────┐ │
│  │  PostgreSQL │  │    Redis    │  │  RabbitMQ           │ │
│  │  (Primary + │  │  (Session & │  │  (Task Queue)       │ │
│  │   Replica)  │  │   Cache)    │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  S3-Compatible Storage (Documents, Images, Backups)    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Prerequisites

### 2.1 Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24.0+ | Containerization |
| Docker Compose | 2.20+ | Local orchestration |
| Kubernetes | 1.28+ | Container orchestration |
| kubectl | 1.28+ | Cluster management |
| Helm | 3.12+ | Package management |
| Git | 2.40+ | Version control |
| Python | 3.11+ | Backend runtime |
| Node.js | 20+ | Frontend runtime |

### 2.2 Infrastructure Requirements

**Cloud Provider:** AWS, GCP, or Azure (managed Kubernetes recommended)

**Minimum Production Cluster:**
- 3 worker nodes (t3.large or equivalent)
- 100 GB persistent storage per node
- Load balancer with static IP
- S3-compatible object storage bucket
- Managed PostgreSQL (RDS, Cloud SQL, or Azure Database)
- Managed Redis (ElastiCache, Memorystore, or Azure Cache)

### 2.3 Access Requirements

- Docker Hub or private container registry access
- Kubernetes cluster admin privileges
- Cloud provider IAM credentials
- Domain name and DNS management access
- TLS certificate (Let's Encrypt or commercial)

---

## 3. Local Development Environment

### 3.1 Repository Setup

```bash
# Clone the repository
git clone https://github.com/ribdigi/ribdigi-erp.git
cd ribdigi-erp

# Create environment file
cp .env.example .env

# Edit .env with local values
nano .env
```

### 3.2 Environment Variables (Local)

```env
# Application
APP_ENV=development
DEBUG=true
SECRET_KEY=dev-secret-key-change-in-production

# Database
DATABASE_URL=postgresql://ribdigi:ribdigi@postgres:5432/ribdigi_erp
POSTGRES_USER=ribdigi
POSTGRES_PASSWORD=ribdigi
POSTGRES_DB=ribdigi_erp

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=

# RabbitMQ
RABBITMQ_URL=amqp://ribdigi:ribdigi@rabbitmq:5672/
RABBITMQ_USER=ribdigi
RABBITMQ_PASS=ribdigi

# Storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=ribdigi-dev

# JWT
JWT_SECRET_KEY=dev-jwt-secret-change-me
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# AI Services
AI_MODEL_PATH=/app/models
ENABLE_AI_FEATURES=true

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3.3 Docker Compose (Local)

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f backend

# Run database migrations
docker-compose exec backend alembic upgrade head

# Seed initial data
docker-compose exec backend python scripts/seed_data.py

# Stop all services
docker-compose down -v
```

**Local Services:**
| Service | Port | Description |
|---------|------|-------------|
| Frontend (Next.js) | http://localhost:3000 | React web application |
| Backend (FastAPI) | http://localhost:8000 | API server + docs at /docs |
| PostgreSQL | localhost:5432 | Primary database |
| Redis | localhost:6379 | Cache & sessions |
| RabbitMQ | localhost:5672 / 15672 | Message queue & management UI |
| MinIO (S3) | localhost:9000 / 9001 | Object storage & console |

---

## 4. Docker Deployment

### 4.1 Image Build Strategy

**Multi-Stage Dockerfile (Backend):**
```dockerfile
# Stage 1: Builder
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Security: Non-root user
RUN groupadd -r ribdigi && useradd -r -g ribdigi ribdigi

# Copy dependencies
COPY --from=builder /root/.local /home/ribdigi/.local
ENV PATH=/home/ribdigi/.local/bin:$PATH

# Copy application
COPY ./app ./app
COPY ./alembic ./alembic
COPY alembic.ini .

# Security: Read-only root filesystem support
RUN mkdir -p /tmp /app/tmp && chmod 777 /tmp /app/tmp

USER ribdigi

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

**Multi-Stage Dockerfile (Frontend):**
```dockerfile
# Stage 1: Dependencies
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

# Stage 2: Builder
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# Stage 3: Runtime
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# Security: Non-root user
RUN addgroup --system --gid 1001 ribdigi
RUN adduser --system --uid 1001 ribdigi

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER ribdigi

EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
```

### 4.2 Build & Push Images

```bash
# Build backend image
docker build -t ribdigi/erp-backend:v1.0.0 -f docker/Dockerfile.backend .

# Build frontend image
docker build -t ribdigi/erp-frontend:v1.0.0 -f docker/Dockerfile.frontend .

# Tag for registry
docker tag ribdigi/erp-backend:v1.0.0 registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
docker tag ribdigi/erp-frontend:v1.0.0 registry.ribdigi.com/ribdigi/erp-frontend:v1.0.0

# Push to registry
docker push registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
docker push registry.ribdigi.com/ribdigi/erp-frontend:v1.0.0
```

### 4.3 Docker Compose (Production-Style)

```yaml
version: '3.8'

services:
  backend:
    image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
    container_name: ribdigi-backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - RABBITMQ_URL=${RABBITMQ_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - S3_ENDPOINT=${S3_ENDPOINT}
    depends_on:
      - postgres
      - redis
      - rabbitmq
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M

  frontend:
    image: registry.ribdigi.com/ribdigi/erp-frontend:v1.0.0
    container_name: ribdigi-frontend
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
    depends_on:
      - backend
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  celery-worker:
    image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
    container_name: ribdigi-celery
    restart: unless-stopped
    command: celery -A app.celery worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - RABBITMQ_URL=${RABBITMQ_URL}
    depends_on:
      - rabbitmq
      - redis
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G

  celery-beat:
    image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
    container_name: ribdigi-celery-beat
    restart: unless-stopped
    command: celery -A app.celery beat --loglevel=info
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - RABBITMQ_URL=${RABBITMQ_URL}
    depends_on:
      - rabbitmq
      - redis

  postgres:
    image: postgres:15-alpine
    container_name: ribdigi-postgres
    restart: unless-stopped
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: ribdigi-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    container_name: ribdigi-rabbitmq
    restart: unless-stopped
    environment:
      - RABBITMQ_DEFAULT_USER=${RABBITMQ_USER}
      - RABBITMQ_DEFAULT_PASS=${RABBITMQ_PASS}
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"

  minio:
    image: minio/minio:latest
    container_name: ribdigi-minio
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      - MINIO_ROOT_USER=${S3_ACCESS_KEY}
      - MINIO_ROOT_PASSWORD=${S3_SECRET_KEY}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"

volumes:
  postgres_data:
  redis_data:
  rabbitmq_data:
  minio_data:
```

---

## 5. Kubernetes Deployment

**MVP fidelity (Stage 26 K1 + Stage 28 G1 + Stage 29 X1):** Versioned Helm chart `helm/ribdigi/` and hardened `k8s/` manifests use live probe paths `GET /api/v1/health` (liveness) and `GET /api/v1/health/ready` (readiness), `ribdigi-secrets` from `.env.production.example`, Celery worker/beat, and migration Job. Operator install/smoke: `ops/k8s/`. Authoritative MVP doc: `docs/K8S_DEPLOY_MVP.md` (`test_k8s_deploy_k1.py`). Stage 28 G1 staging GHA template: `docs/STAGING_GHA_MVP.md`, `ops/k8s/deploy-staging.example.yml` (`test_staging_gha_g1.py`) — not wired into main `ci.yml`. Stage 29 X1 production cutover pack: `docs/CUTOVER_PACK_MVP.md`, `ops/k8s/deploy-production.example.yml`, `ops/launch/cutover-checklist.json` (`test_cutover_pack_x1.py`) — packaging only (`production_cutover_claimed: false`; not forged §7). Live GHA→staging apply and live production cutover / §7 sign-off remain Remaining — do not treat the aspirational replica counts / NetworkPolicy samples below as CI-deployed.


### 5.1 Namespace Structure

```bash
# Create namespaces
kubectl create namespace ribdigi-production
kubectl create namespace ribdigi-staging
kubectl create namespace ribdigi-monitoring
```

### 5.2 Secrets Management

```bash
# Create secrets from environment file
kubectl create secret generic ribdigi-secrets   --from-env-file=.env.production   --namespace=ribdigi-production

# Verify secrets (values are base64 encoded)
kubectl get secrets ribdigi-secrets -n ribdigi-production -o yaml
```

**External Secrets Operator (Production):**
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ribdigi-secrets
  namespace: ribdigi-production
spec:
  refreshInterval: 1h
  secretStoreRef:
    kind: ClusterSecretStore
    name: vault-backend
  target:
    name: ribdigi-secrets
    creationPolicy: Owner
  data:
    - secretKey: DATABASE_URL
      remoteRef:
        key: ribdigi/production
        property: database_url
    - secretKey: JWT_SECRET_KEY
      remoteRef:
        key: ribdigi/production
        property: jwt_secret_key
```

### 5.3 Backend Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ribdigi-backend
  namespace: ribdigi-production
  labels:
    app: ribdigi-backend
    version: v1.0.0
spec:
  replicas: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 2
      maxUnavailable: 1
  selector:
    matchLabels:
      app: ribdigi-backend
  template:
    metadata:
      labels:
        app: ribdigi-backend
        version: v1.0.0
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: backend
          image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
          imagePullPolicy: Always
          ports:
            - containerPort: 8000
              name: http
          envFrom:
            - secretRef:
                name: ribdigi-secrets
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 100
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - ribdigi-backend
                topologyKey: kubernetes.io/hostname
---
apiVersion: v1
kind: Service
metadata:
  name: ribdigi-backend-service
  namespace: ribdigi-production
spec:
  selector:
    app: ribdigi-backend
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
```

### 5.4 Frontend Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ribdigi-frontend
  namespace: ribdigi-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ribdigi-frontend
  template:
    metadata:
      labels:
        app: ribdigi-frontend
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
      containers:
        - name: frontend
          image: registry.ribdigi.com/ribdigi/erp-frontend:v1.0.0
          ports:
            - containerPort: 3000
          env:
            - name: NEXT_PUBLIC_API_URL
              value: "https://api.ribdigi.com"
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "1Gi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: ribdigi-frontend-service
  namespace: ribdigi-production
spec:
  selector:
    app: ribdigi-frontend
  ports:
    - protocol: TCP
      port: 80
      targetPort: 3000
  type: ClusterIP
```

### 5.5 Celery Workers Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ribdigi-celery-worker
  namespace: ribdigi-production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ribdigi-celery-worker
  template:
    metadata:
      labels:
        app: ribdigi-celery-worker
    spec:
      containers:
        - name: celery-worker
          image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
          command: ["celery", "-A", "app.celery", "worker", "--loglevel=info", "--concurrency=4"]
          envFrom:
            - secretRef:
                name: ribdigi-secrets
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ribdigi-celery-beat
  namespace: ribdigi-production
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ribdigi-celery-beat
  template:
    metadata:
      labels:
        app: ribdigi-celery-beat
    spec:
      containers:
        - name: celery-beat
          image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
          command: ["celery", "-A", "app.celery", "beat", "--loglevel=info"]
          envFrom:
            - secretRef:
                name: ribdigi-secrets
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "250m"
```

**MVP fidelity (Stage 29 T1):** Operator cert-manager / TLS packaging — `docs/TLS_INGRESS_PACK_MVP.md`, `ops/k8s/cluster-issuer.example.yaml`, `ops/k8s/ingress-tls.example.yaml` (`test_tls_ingress_t1.py`). The aspirational Ingress YAML below is not proof of live Let’s Encrypt issuance; packaging keeps `letsencrypt_issued: false`.

### 5.6 Ingress Configuration

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ribdigi-ingress
  namespace: ribdigi-production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
spec:
  tls:
    - hosts:
        - app.ribdigi.com
        - api.ribdigi.com
      secretName: ribdigi-tls-secret
  rules:
    - host: app.ribdigi.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ribdigi-frontend-service
                port:
                  number: 80
    - host: api.ribdigi.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: ribdigi-backend-service
                port:
                  number: 80
```

### 5.7 Horizontal Pod Autoscaler (HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: ribdigi-backend-hpa
  namespace: ribdigi-production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: ribdigi-backend
  minReplicas: 5
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

### 5.8 Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ribdigi-backend-network-policy
  namespace: ribdigi-production
spec:
  podSelector:
    matchLabels:
      app: ribdigi-backend
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: ribdigi-frontend
        - namespaceSelector:
            matchLabels:
              name: ribdigi-monitoring
      ports:
        - protocol: TCP
          port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: ribdigi-postgres
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app: ribdigi-redis
      ports:
        - protocol: TCP
          port: 6379
```

---

## 6. CI/CD Pipeline

**MVP fidelity:** Actual CI is `.github/workflows/ci.yml` — backend security/isolation pytest + full suite + frontend build (Stage 18 C1; `test_ci_prod_config_c1.py`). It is intentionally **deploy-free** (no `kubectl` / `helm upgrade`). Stage 26 K1 documents operator Helm/kubectl apply separately (`docs/K8S_DEPLOY_MVP.md`). Stage 28 G1 packages a staging-only GHA template under `ops/k8s/deploy-staging.example.yml` (`docs/STAGING_GHA_MVP.md`, `test_staging_gha_g1.py`) — copy when secrets exist; do not treat the disabled stub as green apply. Stage 29 X1 packages production cutover under `ops/k8s/deploy-production.example.yml` + `docs/CUTOVER_PACK_MVP.md` (`test_cutover_pack_x1.py`) — packaging only (`production_cutover_claimed: false`; not forged §7). The multi-job deploy workflow sketch below remains aspirational Remaining for live cluster execution.


### 6.1 GitHub Actions Workflow

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: registry.ribdigi.com
  BACKEND_IMAGE: ribdigi/erp-backend
  FRONTEND_IMAGE: ribdigi/erp-frontend

jobs:
  test-backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: ribdigi_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Install dependencies
        run: npm ci
      - name: Run linter
        run: npm run lint
      - name: Run tests
        run: npm run test:ci

  security-scan:
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend]
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          format: 'sarif'
          output: 'trivy-results.sarif'
      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'

  build-and-push:
    runs-on: ubuntu-latest
    needs: [test-backend, test-frontend, security-scan]
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Login to Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ secrets.REGISTRY_USERNAME }}
          password: ${{ secrets.REGISTRY_PASSWORD }}
      - name: Build and push backend
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./docker/Dockerfile.backend
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.BACKEND_IMAGE }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.BACKEND_IMAGE }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Build and push frontend
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          file: ./docker/Dockerfile.frontend
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.FRONTEND_IMAGE }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.FRONTEND_IMAGE }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    runs-on: ubuntu-latest
    needs: build-and-push
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Configure kubectl
        uses: azure/setup-kubectl@v3
      - name: Set up Helm
        uses: azure/setup-helm@v3
      - name: Deploy to Staging
        run: |
          helm upgrade --install ribdigi-staging ./helm-chart             --namespace ribdigi-staging             --set backend.image.tag=${{ github.sha }}             --set frontend.image.tag=${{ github.sha }}             --values values-staging.yaml

  deploy-production:
    runs-on: ubuntu-latest
    needs: deploy-staging
    environment: production
    steps:
      - uses: actions/checkout@v4
      - name: Configure kubectl
        uses: azure/setup-kubectl@v3
      - name: Deploy to Production
        run: |
          helm upgrade --install ribdigi-production ./helm-chart             --namespace ribdigi-production             --set backend.image.tag=${{ github.sha }}             --set frontend.image.tag=${{ github.sha }}             --values values-production.yaml
```

### 6.2 Helm Chart Structure

```
helm-chart/
├── Chart.yaml
├── values.yaml
├── values-staging.yaml
├── values-production.yaml
└── templates/
    ├── _helpers.tpl
    ├── backend-deployment.yaml
    ├── frontend-deployment.yaml
    ├── celery-worker-deployment.yaml
    ├── celery-beat-deployment.yaml
    ├── ingress.yaml
    ├── hpa.yaml
    ├── network-policies.yaml
    └── secrets.yaml
```

---

## 7. Database Migration Strategy

### 7.1 Migration Tool: Alembic

```bash
# Generate new migration
alembic revision --autogenerate -m "add_inventory_tracking"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View current version
alembic current

# View migration history
alembic history
```

### 7.2 Migration Best Practices

- **Never modify existing migrations** after they have been applied to staging/production
- **Always test migrations** on a copy of production data before deployment
- **Use transactions** for migrations to enable rollback on failure
- **Add backward-compatible changes first** (e.g., add column → populate → add constraint)
- **Schedule downtime** for destructive migrations (column drops, type changes)

### 7.3 Kubernetes Job for Migrations

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration-job
  namespace: ribdigi-production
spec:
  template:
    spec:
      containers:
        - name: migration
          image: registry.ribdigi.com/ribdigi/erp-backend:v1.0.0
          command: ["alembic", "upgrade", "head"]
          envFrom:
            - secretRef:
                name: ribdigi-secrets
      restartPolicy: OnFailure
```

**Pre-Deploy Hook:**
```bash
# Run migration before deploying new pods
kubectl apply -f k8s/migration-job.yaml
kubectl wait --for=condition=complete job/db-migration-job -n ribdigi-production --timeout=300s
```

---

## 8. Environment Configuration

### 8.1 Configuration Hierarchy

```
Default Config → Environment File → Kubernetes Secrets → Runtime Overrides
```

### 8.2 Environment-Specific Values

| Parameter | Development | Staging | Production |
|-----------|-------------|---------|------------|
| `DEBUG` | `true` | `false` | `false` |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `WARNING` |
| `REPLICAS_BACKEND` | 1 | 2 | 5 |
| `REPLICAS_FRONTEND` | 1 | 2 | 3 |
| `REPLICAS_CELERY` | 1 | 2 | 3 |
| `DB_POOL_SIZE` | 5 | 10 | 20 |
| `RATE_LIMIT` | 1000/min | 300/min | 120/min |
| `SESSION_TTL` | 24h | 24h | 15min |
| `BACKUP_RETENTION` | 7 days | 14 days | 30 days |

### 8.3 Feature Flags

```env
# Module Enablement
ENABLE_POS=true
ENABLE_AI_FEATURES=true
ENABLE_MULTI_STORE=true

# Beta Features
ENABLE_ADVANCED_REPORTS=false
ENABLE_API_V2=false

# Maintenance
MAINTENANCE_MODE=false
MAINTENANCE_MESSAGE="System upgrade in progress"
```

---

## 9. Monitoring & Observability

**MVP fidelity (Stage 26 M1 + Stage 28 A1 + Stage 30 I1):** Live surfaces are `GET /api/v1/health` / `health/ready` and Prometheus-text `GET /api/v1/metrics`, plus structured `ribdigi.request` JSON logs (Stage 18 L1). Versioned operator configs: `ops/prometheus/prometheus.yml`, `ops/prometheus/alerts/ribdigi.yml`, `ops/logging/fluent-bit-ribdigi.conf.example`. Authoritative MVP doc: `docs/OPS_MONITORING_MVP.md` (`test_ops_monitoring_m1.py`). Stage 28 A1 Grafana/Alertmanager examples: `docs/GRAFANA_PACK_MVP.md`, `ops/grafana/` (`test_grafana_pack_a1.py`) — packaging only. Stage 30 I1 incident / on-call pack: `docs/INCIDENT_PACK_MVP.md`, `ops/incident/` (`test_incident_pack_i1.py`) — packaging only (`pagerduty_hosted_claimed: false`). Hosted Grafana / Alertmanager→PagerDuty / live rota / SIEM remain post-MVP operator choices — do not treat the aspirational tables below as deployed-by-default.

### 9.1 Monitoring Stack

| Component | Tool | Purpose |
|-----------|------|---------|
| Metrics | Prometheus + Grafana | Infrastructure and application metrics |
| Logging | Fluent Bit + Elasticsearch + Kibana | Centralized log aggregation |
| Tracing | Jaeger / OpenTelemetry | Distributed request tracing |
| Alerting | Alertmanager + PagerDuty | Incident notification |
| Uptime | Pingdom / UptimeRobot | External health checks |

### 9.2 Key Metrics

**Infrastructure:**
- CPU/Memory utilization per pod
- Disk I/O and storage usage
- Network latency and throughput
- Database connection pool usage

**Application:**
- Request rate, latency (p50, p95, p99), error rate
- JWT token validation failures
- Database query performance (slow query log)
- Cache hit/miss ratio
- Queue depth and processing rate (Celery)
- Tenant-specific resource consumption

**Business:**
- Active users per tenant
- Transaction volume per minute
- AI assistant query volume
- Failed login attempts per IP

### 9.3 Health Check Endpoints

```python
# FastAPI health checks
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@app.get("/ready")
async def readiness_check():
    # Check database connectivity
    await db.execute("SELECT 1")
    # Check Redis connectivity
    await redis.ping()
    return {"status": "ready"}

@app.get("/metrics")
async def metrics():
    # Prometheus metrics endpoint
    return generate_latest()
```

### 9.4 Alerting Rules

```yaml
groups:
  - name: ribdigi-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"

      - alert: DatabaseConnectionExhausted
        expr: pg_stat_activity_count / pg_settings_max_connections > 0.8
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Database connections near limit"

      - alert: CeleryQueueBacklog
        expr: celery_queue_length > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Celery task queue backlog detected"
```

---

## 10. Scaling & High Availability

**MVP load fidelity (Stage 26 C1):** CI smoke + CI capacity profiles via `backend/loadtest/` (`--smoke`, `--ci-capacity`); evidence `/opt/cursor/artifacts/loadtest/stage26_c1_capacity_evidence.json` (`test_load_capacity_c1.py`). Authoritative doc: `docs/LOAD_CAPACITY_MVP.md`. Stage 28 C1 operator ~1000-VU cert pack: `docs/LOAD_CERT_PACK_MVP.md`, `ops/loadtest/` (`test_load_cert_pack_c1.py`) — packaging only. Operator staging ~1000-VU **execution** remains Remaining. Stage 26 D1 locks the ops platform evidence chain (`docs/STAGE_26_FIDELITY.md`, `backend/tests/test_stage26_fidelity_d1.py`) across monitoring, WAL/PITR, Kubernetes/Helm, and load capacity; main `ci.yml` remains deploy-free (Stage 18 C1). Stage 26 H26x exit + freeze: `docs/STAGE_26_EXIT_CRITERIA.md`, ADR-058 (`test_stage26_exit_h26x.py`). Stage 28 D1 staging certification fidelity: `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`) maps R1–C1 packs. Stage 29 D1 operator hardening & cutover fidelity: `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`) maps V1–X1 packs. Stage 29 H29x exit + freeze: `docs/STAGE_29_EXIT_CRITERIA.md`, ADR-064 (`test_stage29_exit_h29x.py`). Stage 30 L1 evidence ledger: `docs/EVIDENCE_LEDGER_MVP.md` (`test_evidence_ledger_l1.py`). Stage 30 D1 go-live support fidelity: `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`) maps L1–A1 packs. Stage 30 H30x exit + freeze: `docs/STAGE_30_EXIT_CRITERIA.md`, ADR-066 (`test_stage30_exit_h30x.py`). Stage 31 D1 commercial MVP closeout fidelity: `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`) maps G1–C1 packs (`docs/MVP_GATE_MATRIX_MVP.md`, `docs/MVP_DECLARATION_MVP.md`, `docs/OPERATOR_REMAINING_MVP.md`); packaging only — no go-live signed claim. Stage 31 H31x exit + freeze: `docs/STAGE_31_EXIT_CRITERIA.md`, ADR-068 (`test_stage31_exit_h31x.py`). Stage 32 D1 commercial MVP handoff fidelity: `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`) maps A1–B1 packs (`docs/ACCEPTANCE_ARCHIVE_MVP.md`, `docs/OPERATOR_HANDOFF_MVP.md`, `docs/RELEASE_NOTES_MVP.md`, `docs/POST_MVP_BACKLOG_MVP.md`); packaging only — no go-live signed claim. Stage 33 D1 commercial MVP continuity fidelity: `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`) maps K1–T1 packs (`docs/RESIDUAL_RISK_MVP.md`, `docs/COMPLIANCE_READINESS_MVP.md`, `docs/FIRST_TENANT_ONBOARDING_MVP.md`, `docs/KNOWLEDGE_TRANSFER_MVP.md`); packaging only — no go-live signed claim. Stage 33 H33x exit + freeze: `docs/STAGE_33_EXIT_CRITERIA.md`, ADR-072 (`test_stage33_exit_h33x.py`). Stage 34 D1 commercial customer assurance fidelity: `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`) maps A1–C1 packs (`docs/ASSURANCE_EVIDENCE_MVP.md`, `docs/COMPLIANCE_QUESTIONNAIRE_MVP.md`); S1/B1 deferred; packaging only — no go-live signed claim. Stage 34 H34x exit + freeze: `docs/STAGE_34_EXIT_CRITERIA.md`, ADR-074 (`test_stage34_exit_h34x.py`). Stage 35 D1 commercial E2E operational smoke fidelity: `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`) maps T1–R1 packs (`docs/E2E_ORG_BOOTSTRAP_MVP.md`, `docs/E2E_USERS_RBAC_MVP.md`, `docs/E2E_PURCHASE_STOCK_MVP.md`, `docs/E2E_SALE_PAYMENT_MVP.md`, `docs/E2E_VERIFY_FINANCIALS_MVP.md`, `docs/E2E_BACKUP_RESTORE_MVP.md`); packaging only — no live E2E smoke / go-live signed claim. Stage 35 H35x exit + freeze: `docs/STAGE_35_EXIT_CRITERIA.md`, ADR-076 (`test_stage35_exit_h35x.py`). Stage 36 open (ADR-077): `docs/STAGE_36_PLAN.md` (`test_stage36_open.py`). Stage 36 D1 commercial assurance completion fidelity: `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`) maps S1–B1 packs (`docs/SUPPORT_SLA_BOUNDARY_MVP.md`, `docs/BILLING_DEFERRED_HONESTY_MVP.md`); packaging only — no live SLA / paid billing claim. Stage 36 H36x exit + freeze: `docs/STAGE_36_EXIT_CRITERIA.md`, ADR-078 (`test_stage36_exit_h36x.py`). Stage 37 open (ADR-079): `docs/STAGE_37_PLAN.md` (`test_stage37_open.py`). Stage 37 P1: `docs/DATA_PORTABILITY_MVP.md` (`test_data_portability_p1.py`). Stage 37 E1: `docs/ERASURE_HONESTY_MVP.md` (`test_erasure_honesty_e1.py`). Stage 37 D1: `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`). Stage 37 H37x exit + freeze: `docs/STAGE_37_EXIT_CRITERIA.md`, ADR-080 (`test_stage37_exit_h37x.py`). Stage 38 open (ADR-081): `docs/STAGE_38_PLAN.md` (`test_stage38_open.py`). Stage 38 V1: `docs/VULN_DISCLOSURE_MVP.md` (`test_vuln_disclosure_v1.py`). Stage 38 B1: `docs/BREACH_NOTIFICATION_MVP.md` (`test_breach_notification_b1.py`). Stage 38 D1: `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`). Stage 38 H38x exit + freeze: `docs/STAGE_38_EXIT_CRITERIA.md`, ADR-082 (`test_stage38_exit_h38x.py`). Stage 39 open (ADR-083): `docs/STAGE_39_PLAN.md` (`test_stage39_open.py`). Stage 39 P1: `docs/DPA_SUBPROCESSOR_MVP.md` (`test_dpa_subprocessor_p1.py`). Stage 39 A1: `docs/MSA_ADDENDUM_MVP.md` (`test_msa_addendum_a1.py`). Stage 39 D1: `docs/STAGE_39_FIDELITY.md` (`test_stage39_fidelity_d1.py`). Stage 39 H39x exit + freeze: `docs/STAGE_39_EXIT_CRITERIA.md Stage 40 open: `docs/STAGE_40_PLAN.md`, ADR-085 (`test_stage40_open.py`). Stage 40 U1: `docs/STATUS_UPTIME_MVP.md` (`test_status_uptime_u1.py`). Stage 40 S1 SBOM/dependency disclosure honesty Complete (MVP) Stage 40 D1 availability & supply-chain fidelity Complete (MVP) Stage 40 exit met — `docs/STAGE_40_EXIT_CRITERIA.md`, ADR-086 (`test_stage40_exit_h40x.py`) Stage 41 open: `docs/STAGE_41_PLAN.md`, ADR-087 (`test_stage41_open.py`). Stage 41 A1 accessibility statement honesty Complete (MVP) Stage 41 C1 change/maintenance governance honesty Complete (MVP) Stage 41 D1 accessibility & change governance fidelity Complete (MVP) Stage 41 exit met — `docs/STAGE_41_EXIT_CRITERIA.md`, ADR-088 (`test_stage41_exit_h41x.py`) Stage 42 open: `docs/STAGE_42_PLAN.md`, ADR-089 (`test_stage42_open.py`). Stage 42 A1 AI use disclosure honesty Complete (MVP) Stage 42 P1 AI model/provider boundary honesty Complete (MVP) Stage 42 D1 AI transparency fidelity Complete (MVP) Stage 42 exit met — `docs/STAGE_42_EXIT_CRITERIA.md`, ADR-090 (`test_stage42_exit_h42x.py`) Stage 43 open: `docs/STAGE_43_PLAN.md`, ADR-091 (`test_stage43_open.py`). Stage 43 T1 ToS / AUP honesty Complete (MVP) — `docs/TOS_AUP_MVP.md`, `ops/mvp/tos-aup.json` (`test_tos_aup_t1.py`). Stage 43 C1 Cookie / privacy notice honesty Complete (MVP) — `docs/COOKIE_PRIVACY_NOTICE_MVP.md`, `ops/mvp/cookie-privacy-notice.json` (`test_cookie_privacy_notice_c1.py`). Stage 43 D1 commercial legal notice fidelity Complete (MVP) — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`). Stage 43 exit met — `docs/STAGE_43_EXIT_CRITERIA.md`, ADR-092 (`test_stage43_exit_h43x.py`). Stage 44 open: `docs/STAGE_44_PLAN.md`, ADR-093 (`test_stage44_open.py`). Stage 44 R1 data residency / localization honesty Complete (MVP) — `docs/DATA_RESIDENCY_MVP.md`, `ops/mvp/data-residency.json` (`test_data_residency_r1.py`). Stage 44 E1 encryption / key-management honesty Complete (MVP) — `docs/ENCRYPTION_KMS_MVP.md`, `ops/mvp/encryption-kms.json` (`test_encryption_kms_e1.py`). Stage 44 D1 commercial data trust fidelity Complete (MVP) — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`). Stage 44 exit met — `docs/STAGE_44_EXIT_CRITERIA.md`, ADR-094 (`test_stage44_exit_h44x.py`). Stage 45 open: `docs/STAGE_45_PLAN.md`, ADR-095 (`test_stage45_open.py`). Stage 45 O1 RTO / RPO recovery objectives honesty Complete (MVP) — `docs/RTO_RPO_MVP.md`, `ops/mvp/rto-rpo.json` (`test_rto_rpo_o1.py`). Stage 45 T1 data retention / return honesty Complete (MVP) — `docs/DATA_RETENTION_RETURN_MVP.md`, `ops/mvp/data-retention-return.json` (`test_data_retention_return_t1.py`). Stage 45 D1 commercial continuity & exit fidelity Complete (MVP) — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`). Stage 45 exit met — `docs/STAGE_45_EXIT_CRITERIA.md`, ADR-096 (`test_stage45_exit_h45x.py`). Stage 46 open: `docs/STAGE_46_PLAN.md`, ADR-097 (`test_stage46_open.py`). Stage 46 L1 limitation of liability / indemnity honesty Complete (MVP) — `docs/LIABILITY_INDEMNITY_MVP.md`, `ops/mvp/liability-indemnity.json` (`test_liability_indemnity_l1.py`). Stage 46 W1 service credit / warranty honesty Complete (MVP) — `docs/SERVICE_CREDIT_WARRANTY_MVP.md`, `ops/mvp/service-credit-warranty.json` (`test_service_credit_warranty_w1.py`). Stage 46 D1 commercial liability & remedy fidelity Complete (MVP) — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`). Stage 46 exit met — `docs/STAGE_46_EXIT_CRITERIA.md`, ADR-098 (`test_stage46_exit_h46x.py`). Stage 47 open: `docs/STAGE_47_PLAN.md`, ADR-099 (`test_stage47_open.py`). Stage 47 I1 cyber insurance / COI honesty Complete (MVP) — `docs/CYBER_INSURANCE_MVP.md`, `ops/mvp/cyber-insurance.json` (`test_cyber_insurance_i1.py`). Stage 47 A1 customer audit rights honesty Complete (MVP) — `docs/CUSTOMER_AUDIT_RIGHTS_MVP.md`, `ops/mvp/customer-audit-rights.json` (`test_customer_audit_rights_a1.py`). Stage 47 D1 commercial insurance & audit fidelity Complete (MVP) — `docs/STAGE_47_FIDELITY.md` (`test_stage47_fidelity_d1.py`). Stage 47 exit met — `docs/STAGE_47_EXIT_CRITERIA.md`, ADR-100 (`test_stage47_exit_h47x.py`). Stage 48 open: `docs/STAGE_48_PLAN.md`, ADR-101 (`test_stage48_open.py`). Stage 48 P1 professional services / SOW honesty Complete (MVP) — `docs/PROFESSIONAL_SERVICES_SOW_MVP.md`, `ops/mvp/professional-services-sow.json` (`test_professional_services_sow_p1.py`). Stage 48 T1 customer training / certification honesty Complete (MVP) — `docs/CUSTOMER_TRAINING_CERT_MVP.md`, `ops/mvp/customer-training-cert.json` (`test_customer_training_cert_t1.py`). Stage 48 D1 commercial services fidelity Complete (MVP) — `docs/STAGE_48_FIDELITY.md` (`test_stage48_fidelity_d1.py`). Stage 48 exit met — `docs/STAGE_48_EXIT_CRITERIA.md`, ADR-102 (`test_stage48_exit_h48x.py`). Stage 49 open: `docs/STAGE_49_PLAN.md`, ADR-103 (`test_stage49_open.py`). Stage 49 R1 partner / reseller terms honesty Complete (MVP) — `docs/PARTNER_RESELLER_MVP.md`, `ops/mvp/partner-reseller.json` (`test_partner_reseller_r1.py`). Stage 49 L1 pricing transparency honesty Complete (MVP) — `docs/PRICING_TRANSPARENCY_MVP.md`, `ops/mvp/pricing-transparency.json`; evidence `/opt/cursor/artifacts/launch/stage49_l1_pricing_transparency.json` (`test_pricing_transparency_l1.py`). Stage 49 D1 commercial channel & pricing fidelity Complete (MVP) — `docs/STAGE_49_FIDELITY.md` (`test_stage49_fidelity_d1.py`). Stage 49 exit met — `docs/STAGE_49_EXIT_CRITERIA.md`, ADR-104 (`test_stage49_exit_h49x.py`). Stage 50 open: `docs/STAGE_50_PLAN.md`, ADR-105 (`test_stage50_open.py`). Stage 50 R1 referral program honesty Complete (MVP) — `docs/REFERRAL_PROGRAM_MVP.md`, `ops/mvp/referral-program.json` (`test_referral_program_r1.py`). Stage 50 F1 freemium trial honesty Complete (MVP) — `docs/FREEMIUM_TRIAL_MVP.md`, `ops/mvp/freemium-trial.json`; evidence `/opt/cursor/artifacts/launch/stage50_f1_freemium_trial.json` (`test_freemium_trial_f1.py`). Stage 50 D1 commercial acquisition & trial fidelity Complete (MVP) — `docs/STAGE_50_FIDELITY.md` (`test_stage50_fidelity_d1.py`). Stage 50 exit met — `docs/STAGE_50_EXIT_CRITERIA.md`, ADR-106 (`test_stage50_exit_h50x.py`). Stage 51 open: `docs/STAGE_51_PLAN.md`, ADR-107 (`test_stage51_open.py`). Stage 51 M1 marketplace presence honesty Complete (MVP) — `docs/MARKETPLACE_PRESENCE_MVP.md`, `ops/mvp/marketplace-presence.json` (`test_marketplace_presence_m1.py`). Stage 51 A1 add-on services honesty Complete (MVP) — `docs/ADDON_SERVICES_MVP.md`, `ops/mvp/addon-services.json`; evidence `/opt/cursor/artifacts/launch/stage51_a1_addon_services.json` (`test_addon_services_a1.py`). Stage 51 D1 commercial marketplace & add-ons fidelity Complete (MVP) — `docs/STAGE_51_FIDELITY.md` (`test_stage51_fidelity_d1.py`). Stage 51 exit met — `docs/STAGE_51_EXIT_CRITERIA.md`, ADR-108 (`test_stage51_exit_h51x.py`). Stage 52 open: `docs/STAGE_52_PLAN.md`, ADR-109 (`test_stage52_open.py`). Stage 52 I1 industry partnerships honesty Complete (MVP) — `docs/INDUSTRY_PARTNERSHIPS_MVP.md`, `ops/mvp/industry-partnerships.json` (`test_industry_partnerships_i1.py`). Stage 52 R1 subscription renewal / annual discount honesty Complete (MVP) — `docs/SUBSCRIPTION_RENEWAL_MVP.md`, `ops/mvp/subscription-renewal.json`; evidence `/opt/cursor/artifacts/launch/stage52_r1_subscription_renewal.json` (`test_subscription_renewal_r1.py`). Stage 52 D1 commercial partnerships & renewal fidelity Complete (MVP) — `docs/STAGE_52_FIDELITY.md` (`test_stage52_fidelity_d1.py`). Stage 52 exit met — `docs/STAGE_52_EXIT_CRITERIA.md`, ADR-110 (`test_stage52_exit_h52x.py`). Stage 53 open: `docs/STAGE_53_PLAN.md`, ADR-111 (`test_stage53_open.py`). Stage 53 A1 API & integration commercial honesty Complete (MVP) — `docs/API_INTEGRATION_COMMERCIAL_MVP.md`, `ops/mvp/api-integration-commercial.json` (`test_api_integration_commercial_a1.py`). Stage 53 C1 cancellation / refund / churn policy honesty Complete (MVP) — `docs/CANCELLATION_CHURN_MVP.md`, `ops/mvp/cancellation-churn.json`; evidence `/opt/cursor/artifacts/launch/stage53_c1_cancellation_churn.json` (`test_cancellation_churn_c1.py`). Stage 53 D1 commercial API & lifecycle fidelity Complete (MVP) — `docs/STAGE_53_FIDELITY.md` (`test_stage53_fidelity_d1.py`). Stage 53 exit met — `docs/STAGE_53_EXIT_CRITERIA.md`, ADR-112 (`test_stage53_exit_h53x.py`). Stage 54 open: `docs/STAGE_54_PLAN.md`, ADR-113 (`test_stage54_open.py`). Stage 54 M1 digital marketing / case studies / testimonials honesty Complete (MVP) — `docs/DIGITAL_MARKETING_MVP.md`, `ops/mvp/digital-marketing.json` (`test_digital_marketing_m1.py`). Stage 54 S1 direct sales honesty Complete (MVP) — `docs/DIRECT_SALES_MVP.md`, `ops/mvp/direct-sales.json`; evidence `/opt/cursor/artifacts/launch/stage54_s1_direct_sales.json` (`test_direct_sales_s1.py`). Stage 54 D1 commercial go-to-market fidelity Complete (MVP) — `docs/STAGE_54_FIDELITY.md` (`test_stage54_fidelity_d1.py`). Stage 54 exit met — `docs/STAGE_54_EXIT_CRITERIA.md`, ADR-114 (`test_stage54_exit_h54x.py`). Stage 55 open: `docs/STAGE_55_PLAN.md`, ADR-115 (`test_stage55_open.py`). Stage 55 W1 white-label licensing commercial honesty Complete (MVP) — `docs/WHITE_LABEL_LICENSING_MVP.md`, `ops/mvp/white-label-licensing.json` (`test_white_label_licensing_w1.py`). Stage 55 U1 unit economics / competitive positioning honesty Complete (MVP) — `docs/UNIT_ECONOMICS_POSITIONING_MVP.md`, `ops/mvp/unit-economics-positioning.json`; evidence `/opt/cursor/artifacts/launch/stage55_u1_unit_economics_positioning.json` (`test_unit_economics_positioning_u1.py`). Stage 55 D1 commercial licensing & positioning fidelity Complete (MVP) — `docs/STAGE_55_FIDELITY.md` (`test_stage55_fidelity_d1.py`). Stage 55 exit met — `docs/STAGE_55_EXIT_CRITERIA.md`, ADR-116 (`test_stage55_exit_h55x.py`). Stage 56 open: `docs/STAGE_56_PLAN.md`, ADR-117 (`test_stage56_open.py`). Stage 56 O1 implementation & onboarding commercial honesty Complete (MVP) — `docs/IMPLEMENTATION_ONBOARDING_MVP.md`, `ops/mvp/implementation-onboarding.json` (`test_implementation_onboarding_o1.py`). Stage 56 G1 geographic expansion honesty Complete (MVP) — `docs/GEOGRAPHIC_EXPANSION_MVP.md`, `ops/mvp/geographic-expansion.json` (`test_geographic_expansion_g1.py`). Stage 56 D1 commercial onboarding & expansion fidelity Complete (MVP) — `docs/STAGE_56_FIDELITY.md` (`test_stage56_fidelity_d1.py`). Stage 56 exit met — `docs/STAGE_56_EXIT_CRITERIA.md`, ADR-118 (`test_stage56_exit_h56x.py`). Stage 57 open: `docs/STAGE_57_PLAN.md`, ADR-119 (`test_stage57_open.py`). Stage 57 A1 mobile app GTM honesty Complete (MVP) — `docs/MOBILE_APP_GTM_MVP.md`, `ops/mvp/mobile-app-gtm.json` (`test_mobile_app_gtm_a1.py`). Stage 57 K1 success metrics honesty Complete (MVP) — `docs/SUCCESS_METRICS_MVP.md`, `ops/mvp/success-metrics.json` (`test_success_metrics_k1.py`). Stage 57 D1 commercial mobile & metrics fidelity Complete (MVP) — `docs/STAGE_57_FIDELITY.md` (`test_stage57_fidelity_d1.py`). Stage 57 exit met — `docs/STAGE_57_EXIT_CRITERIA.md`, ADR-120 (`test_stage57_exit_h57x.py`). Stage 58 open: `docs/STAGE_58_PLAN.md`, ADR-121 (`test_stage58_open.py`). Stage 58 B1 business metrics honesty Complete (MVP) — `docs/BUSINESS_METRICS_MVP.md`, `ops/mvp/business-metrics.json` (`test_business_metrics_b1.py`). Stage 58 I1 AI metrics honesty Complete (MVP) — `docs/AI_METRICS_MVP.md`, `ops/mvp/ai-metrics.json` (`test_ai_metrics_i1.py`). Stage 58 D1 commercial business & AI metrics fidelity Complete (MVP) — `docs/STAGE_58_FIDELITY.md` (`test_stage58_fidelity_d1.py`). Stage 58 exit met — `docs/STAGE_58_EXIT_CRITERIA.md`, ADR-122 (`test_stage58_exit_h58x.py`). Stage 59 open: `docs/STAGE_59_PLAN.md`, ADR-123 (`test_stage59_open.py`). Stage 59 E1 e-commerce integration honesty Complete (MVP) — `docs/ECOMMERCE_INTEGRATION_MVP.md`, `ops/mvp/ecommerce-integration.json` (`test_ecommerce_integration_e1.py`). Stage 59 C1 CRM commercial honesty Complete (MVP) — `docs/CRM_COMMERCIAL_MVP.md`, `ops/mvp/crm-commercial.json` (`test_crm_commercial_c1.py`). Stage 59 D1 commercial channel extensions fidelity Complete (MVP) — `docs/STAGE_59_FIDELITY.md` (`test_stage59_fidelity_d1.py`). Stage 59 exit met — `docs/STAGE_59_EXIT_CRITERIA.md`, ADR-124 (`test_stage59_exit_h59x.py`). Stage 60 open: `docs/STAGE_60_PLAN.md`, ADR-125 (`test_stage60_open.py`). Stage 60 M1 advanced manufacturing honesty Complete (MVP) — `docs/ADVANCED_MANUFACTURING_MVP.md`, `ops/mvp/advanced-manufacturing.json` (`test_advanced_manufacturing_m1.py`). Stage 60 T1 multi-country tax honesty Complete (MVP) — `docs/MULTI_COUNTRY_TAX_MVP.md`, `ops/mvp/multi-country-tax.json` (`test_multi_country_tax_t1.py`). Stage 60 D1 commercial manufacturing & tax fidelity Complete (MVP) — `docs/STAGE_60_FIDELITY.md` (`test_stage60_fidelity_d1.py`). Stage 60 exit met — `docs/STAGE_60_EXIT_CRITERIA.md`, ADR-126 (`test_stage60_exit_h60x.py`). Stage 61 open: `docs/STAGE_61_PLAN.md`, ADR-127 (`test_stage61_open.py`). Stage 61 F1 embedded fintech honesty Complete (MVP) — `docs/EMBEDDED_FINTECH_MVP.md`, `ops/mvp/embedded-fintech.json` (`test_embedded_fintech_f1.py`). Stage 61 S1 supply chain integration honesty Complete (MVP) — `docs/SUPPLY_CHAIN_INTEGRATION_MVP.md`, `ops/mvp/supply-chain-integration.json` (`test_supply_chain_integration_s1.py`). Stage 61 D1 commercial fintech & supply-chain fidelity Complete (MVP) — `docs/STAGE_61_FIDELITY.md` (`test_stage61_fidelity_d1.py`). Stage 61 exit met — `docs/STAGE_61_EXIT_CRITERIA.md`, ADR-128 (`test_stage61_exit_h61x.py`). Stage 62 open: `docs/STAGE_62_PLAN.md`, ADR-129 (`test_stage62_open.py`). Stage 62 I1 IoT integration honesty Complete (MVP) — `docs/IOT_INTEGRATION_MVP.md`, `ops/mvp/iot-integration.json` (`test_iot_integration_i1.py`). Stage 62 A1 AI model marketplace honesty Complete (MVP) — `docs/AI_MODEL_MARKETPLACE_MVP.md`, `ops/mvp/ai-model-marketplace.json` (`test_ai_model_marketplace_a1.py`). Stage 62 D1 commercial IoT & AI marketplace fidelity Complete (MVP) — `docs/STAGE_62_FIDELITY.md` (`test_stage62_fidelity_d1.py`). Stage 62 exit met — `docs/STAGE_62_EXIT_CRITERIA.md`, ADR-130 (`test_stage62_exit_h62x.py`). Stage 63 open: `docs/STAGE_63_PLAN.md`, ADR-131 (`test_stage63_open.py`). Stage 63 P1 IPO readiness honesty Complete (MVP) — `docs/IPO_READINESS_MVP.md`, `ops/mvp/ipo-readiness.json` (`test_ipo_readiness_p1.py`). Stage 63 G1 global scale honesty Complete (MVP) — `docs/GLOBAL_SCALE_MVP.md`, `ops/mvp/global-scale.json` (`test_global_scale_g1.py`). Stage 63 D1 commercial capital & scale fidelity Complete (MVP) — `docs/STAGE_63_FIDELITY.md` (`test_stage63_fidelity_d1.py`). Stage 63 exit met — `docs/STAGE_63_EXIT_CRITERIA.md`, ADR-132 (`test_stage63_exit_h63x.py`). Stage 64 open: `docs/STAGE_64_PLAN.md`, ADR-133 (`test_stage64_open.py`). Stage 64 B1 Advanced BI honesty Complete (MVP) — `docs/ADVANCED_BI_MVP.md`, `ops/mvp/advanced-bi.json` (`test_advanced_bi_b1.py`). Stage 64 F1 Franchise & chain enterprise honesty Complete (MVP) — `docs/FRANCHISE_CHAIN_MVP.md`, `ops/mvp/franchise-chain.json` (`test_franchise_chain_f1.py`). Stage 64 D1 commercial analytics & franchise fidelity Complete (MVP) — `docs/STAGE_64_FIDELITY.md` (`test_stage64_fidelity_d1.py`). Stage 64 exit met — `docs/STAGE_64_EXIT_CRITERIA.md`, ADR-134 (`test_stage64_exit_h64x.py`). Stage 65 open: `docs/STAGE_65_PLAN.md`, ADR-135 (`test_stage65_open.py`). Stage 65 R1 Release pipeline honesty Complete (MVP) — `docs/RELEASE_PIPELINE_MVP.md`, `ops/mvp/release-pipeline.json` (`test_release_pipeline_r1.py`). Stage 65 P1 Controlled business pilot honesty Complete (MVP) — `docs/BUSINESS_PILOT_MVP.md`, `ops/mvp/business-pilot.json` (`test_business_pilot_p1.py`). Stage 65 D1 MVP release-candidate fidelity Complete (MVP) — `docs/STAGE_65_FIDELITY.md` (`test_stage65_fidelity_d1.py`). Stage 65 H65x exit + freeze: `docs/STAGE_65_EXIT_CRITERIA.md`, ADR-136 (`test_stage65_exit_h65x.py`). Stage 66 open: `docs/STAGE_66_PLAN.md`, ADR-138 (`test_stage66_open.py`). Stage 66 L1 Production launch honesty Complete (MVP) — `docs/PRODUCTION_LAUNCH_MVP.md`, `ops/mvp/production-launch.json` (`test_production_launch_l1.py`). Stage 66 T1 First tenant go-live honesty Complete (MVP) — `docs/FIRST_TENANT_GOLIVE_MVP.md`, `ops/mvp/first-tenant-golive.json` (`test_first_tenant_golive_t1.py`). Stage 66 D1 MVP production-launch fidelity Complete (MVP) — `docs/STAGE_66_FIDELITY.md` (`test_stage66_fidelity_d1.py`). Stage 66 H66x exit + freeze: `docs/STAGE_66_EXIT_CRITERIA.md`, ADR-139 (`test_stage66_exit_h66x.py`). Stage 67 open: `docs/STAGE_67_PLAN.md`, ADR-140 (`test_stage67_open.py`). Stage 67 H1 Production hypercare honesty Complete (MVP) — `docs/PRODUCTION_HYPERCARE_MVP.md`, `ops/mvp/production-hypercare.json` (`test_production_hypercare_h1.py`). Stage 67 C1 Post-launch continuity honesty Complete (MVP) — `docs/POST_LAUNCH_CONTINUITY_MVP.md`, `ops/mvp/post-launch-continuity.json` (`test_post_launch_continuity_c1.py`). Stage 67 D1 MVP post-launch continuity fidelity Complete (MVP) — `docs/STAGE_67_FIDELITY.md` (`test_stage67_fidelity_d1.py`). Stage 67 H67x exit + freeze: `docs/STAGE_67_EXIT_CRITERIA.md`, ADR-141 (`test_stage67_exit_h67x.py`). Stage 68 open: `docs/STAGE_68_PLAN.md`, ADR-142 (`test_stage68_open.py`). Stage 68 H1 Ribdigi House console honesty Complete (MVP) — `docs/RIBDIGI_HOUSE_CONSOLE_MVP.md`, `ops/mvp/ribdigi-house-console.json` (`test_ribdigi_house_console_h1.py`). Stage 68 T1 Tenant Company console honesty Complete (MVP) — `docs/TENANT_COMPANY_CONSOLE_MVP.md`, `ops/mvp/tenant-company-console.json` (`test_tenant_company_console_t1.py`). Stage 68 D1 Platform ↔ Tenant console fidelity Complete (MVP) — `docs/STAGE_68_FIDELITY.md` (`test_stage68_fidelity_d1.py`). Stage 68 H68x exit + freeze: `docs/STAGE_68_EXIT_CRITERIA.md`, ADR-143 (`test_stage68_exit_h68x.py`). Stage 69 open: `docs/STAGE_69_PLAN.md`, ADR-144 (`test_stage69_open.py`). Stage 69 V1 Pre-flight verification honesty Complete (MVP) — `docs/PREFLIGHT_VERIFICATION_MVP.md`, `ops/mvp/preflight-verification.json` (`test_preflight_verification_v1.py`). Stage 69 A1 Go-live attestation honesty Complete (MVP) — `docs/GOLIVE_ATTESTATION_MVP.md`, `ops/mvp/golive-attestation.json` (`test_golive_attestation_a1.py`). Honesty: `section_7_signed` / `attestation_claimed` / `go_live_claimed` remain false (packaging ≠ §7 signed). Stage 69 D1 Commercial Go-Live fidelity Complete (MVP) — `docs/STAGE_69_FIDELITY.md` (`test_stage69_fidelity_d1.py`); maps V1–A1. Stage 69 H69x exit + freeze Complete (MVP) — `docs/STAGE_69_EXIT_CRITERIA.md`, ADR-145 (`test_stage69_exit_h69x.py`). Stage 70 open: `docs/STAGE_70_PLAN.md`, ADR-146 (`test_stage70_open.py`). Stage 70 F1 First commercial day ops honesty Complete (MVP) — `docs/FIRST_COMMERCIAL_DAY_MVP.md`, `ops/mvp/first-commercial-day.json` (`test_first_commercial_day_f1.py`). Honesty: `first_commercial_day_claimed` / `commercial_day_ops_live_claimed` remain false (packaging ≠ first-day live). Stage 70 G1 Commercial go-live closeout honesty Complete (MVP) — `docs/COMMERCIAL_GOLIVE_CLOSEOUT_MVP.md`, `ops/mvp/commercial-golive-closeout.json` (`test_commercial_golive_closeout_g1.py`). Honesty: `go_live_claimed` / `commercial_golive_closeout_claimed` remain false (packaging ≠ go-live). Stage 70 D1 First Commercial Day fidelity Complete (MVP) — `docs/STAGE_70_FIDELITY.md` (`test_stage70_fidelity_d1.py`); maps F1–G1. Stage 70 H70x exit + freeze Complete (MVP) — `docs/STAGE_70_EXIT_CRITERIA.md`, ADR-147 (`test_stage70_exit_h70x.py`). Stage 71 open: `docs/STAGE_71_PLAN.md`, ADR-148 (`test_stage71_open.py`). Stage 71 S1 Steady-state commercial ops honesty Complete (MVP) — `docs/STEADY_STATE_OPS_MVP.md`, `ops/mvp/steady-state-ops.json` (`test_steady_state_ops_s1.py`). Honesty: `steady_state_ops_claimed` / `commercial_acceptance_claimed` remain false (packaging ≠ steady-state live). Stage 71 A1 Commercial acceptance gate honesty Complete (MVP) — `docs/COMMERCIAL_ACCEPTANCE_MVP.md`, `ops/mvp/commercial-acceptance.json` (`test_commercial_acceptance_a1.py`). Honesty: `commercial_acceptance_claimed` / `go_live_claimed` remain false (packaging ≠ acceptance Complete). Stage 71 D1 Commercial Steady-State fidelity Complete (MVP) — `docs/STAGE_71_FIDELITY.md` (`test_stage71_fidelity_d1.py`); maps S1–A1. Stage 71 H71x exit + freeze Complete (MVP) — `docs/STAGE_71_EXIT_CRITERIA.md`, ADR-149 (`test_stage71_exit_h71x.py`). Stage 72 open: `docs/STAGE_72_PLAN.md`, ADR-150 (`test_stage72_open.py`). Stage 72 R1 Commercial residual remaining honesty Complete (MVP) — `docs/COMMERCIAL_RESIDUAL_MVP.md`, `ops/mvp/commercial-residual.json` (`test_commercial_residual_r1.py`). Stage 72 P1 Commercial packaging archive honesty Complete (MVP) — `docs/COMMERCIAL_PACKAGING_ARCHIVE_MVP.md`, `ops/mvp/commercial-packaging-archive.json` (`test_commercial_packaging_archive_p1.py`). Stage 72 D1 Commercial Packaging Closeout fidelity Complete (MVP) — `docs/STAGE_72_FIDELITY.md` (`test_stage72_fidelity_d1.py`); maps R1–P1. Stage 72 H72x exit + freeze Complete (MVP) — `docs/STAGE_72_EXIT_CRITERIA.md`, ADR-151 (`test_stage72_exit_h72x.py`). Stage 73 open: `docs/STAGE_73_PLAN.md`, ADR-152 (`test_stage73_open.py`). Stage 73 E1 Commercial evidence chain honesty Complete (MVP) — `docs/COMMERCIAL_EVIDENCE_CHAIN_MVP.md`, `ops/mvp/commercial-evidence-chain.json` (`test_commercial_evidence_chain_e1.py`). Stage 73 A1 Commercial assurance boundary honesty Complete (MVP) — `docs/COMMERCIAL_ASSURANCE_MVP.md`, `ops/mvp/commercial-assurance.json` (`test_commercial_assurance_a1.py`). Stage 73 D1 Commercial Assurance fidelity Complete (MVP) — `docs/STAGE_73_FIDELITY.md` (`test_stage73_fidelity_d1.py`); maps E1–A1. Stage 73 H73x exit + freeze Complete (MVP) — `docs/STAGE_73_EXIT_CRITERIA.md`, ADR-153 (`test_stage73_exit_h73x.py`). Stage 74 open: `docs/STAGE_74_PLAN.md`, ADR-154 (`test_stage74_open.py`). Stage 74 S1 Commercial support boundary honesty Complete (MVP) — `docs/COMMERCIAL_SUPPORT_MVP.md`, `ops/mvp/commercial-support.json` (`test_commercial_support_s1.py`). Stage 74 U1 Commercial status boundary honesty Complete (MVP) — `docs/COMMERCIAL_STATUS_MVP.md`, `ops/mvp/commercial-status.json` (`test_commercial_status_u1.py`). Stage 74 D1 Commercial Operator Boundary fidelity Complete (MVP) — `docs/STAGE_74_FIDELITY.md` (`test_stage74_fidelity_d1.py`); maps S1–U1. Stage 74 H74x exit + freeze Complete (MVP) — `docs/STAGE_74_EXIT_CRITERIA.md`, ADR-155 (`test_stage74_exit_h74x.py`). Stage 75 C1 commercial security contact honesty Complete (MVP) — `docs/COMMERCIAL_SECURITY_CONTACT_MVP.md`, `ops/mvp/commercial-security-contact.json` (`test_commercial_security_contact_c1.py`); security contact live Remaining. Stage 75 P1 commercial privacy notice honesty Complete (MVP) — `docs/COMMERCIAL_PRIVACY_NOTICE_MVP.md`, `ops/mvp/commercial-privacy-notice.json` (`test_commercial_privacy_notice_p1.py`); privacy notice live Remaining. Stage 75 D1 Commercial Trust Boundary fidelity Complete (MVP) — `docs/STAGE_75_FIDELITY.md` (`test_stage75_fidelity_d1.py`); maps C1–P1. Stage 75 H75x exit + freeze Complete (MVP) — `docs/STAGE_75_EXIT_CRITERIA.md`, ADR-157 (`test_stage75_exit_h75x.py`). Stage 76 T1 commercial terms honesty Complete (MVP) — `docs/COMMERCIAL_TERMS_MVP.md`, `ops/mvp/commercial-terms.json` (`test_commercial_terms_t1.py`); signed ToS Remaining. Stage 76 B1 commercial billing deferred honesty Complete (MVP) — `docs/COMMERCIAL_BILLING_DEFERRED_MVP.md`, `ops/mvp/commercial-billing-deferred.json` (`test_commercial_billing_deferred_b1.py`); paid billing Remaining. Stage 76 D1 Commercial Contract Boundary fidelity Complete (MVP) — `docs/STAGE_76_FIDELITY.md` (`test_stage76_fidelity_d1.py`); maps T1–B1. Stage 76 H76x exit + freeze Complete (MVP) — `docs/STAGE_76_EXIT_CRITERIA.md`, ADR-159 (`test_stage76_exit_h76x.py`). Stage 77 A1 commercial DPA honesty Complete (MVP) — `docs/COMMERCIAL_DPA_MVP.md`, `ops/mvp/commercial-dpa.json` (`test_commercial_dpa_a1.py`); signed DPA Remaining. Stage 77 L1 commercial liability honesty Complete (MVP) — `docs/COMMERCIAL_LIABILITY_MVP.md`, `ops/mvp/commercial-liability.json` (`test_commercial_liability_l1.py`); liability cap signed Remaining. Stage 77 D1 Commercial Legal Envelope fidelity Complete (MVP) — `docs/STAGE_77_FIDELITY.md` (`test_stage77_fidelity_d1.py`); maps A1–L1. Stage 77 H77x exit + freeze Complete (MVP) — `docs/STAGE_77_EXIT_CRITERIA.md`, ADR-161 (`test_stage77_exit_h77x.py`). Stage 78 P1 commercial pricing honesty Complete (MVP) — `docs/COMMERCIAL_PRICING_MVP.md`, `ops/mvp/commercial-pricing.json` (`test_commercial_pricing_p1.py`); public pricing portal Remaining. Stage 78 S1 commercial professional services honesty Complete (MVP) — `docs/COMMERCIAL_PROFESSIONAL_SERVICES_MVP.md`, `ops/mvp/commercial-professional-services.json` (`test_commercial_professional_services_s1.py`); signed SOW Remaining. Stage 78 D1 Commercial Procurement Boundary fidelity Complete (MVP) — `docs/STAGE_78_FIDELITY.md` (`test_stage78_fidelity_d1.py`); maps P1–S1. Stage 78 H78x exit + freeze Complete (MVP) — `docs/STAGE_78_EXIT_CRITERIA.md`, ADR-163 (`test_stage78_exit_h78x.py`). Stage 79 R1 commercial data retention honesty Complete (MVP) — `docs/COMMERCIAL_DATA_RETENTION_MVP.md`, `ops/mvp/commercial-data-retention.json` (`test_commercial_data_retention_r1.py`); data return portal Remaining. Stage 79 A1 commercial customer audit honesty Complete (MVP) — `docs/COMMERCIAL_CUSTOMER_AUDIT_MVP.md`, `ops/mvp/commercial-customer-audit.json` (`test_commercial_customer_audit_a1.py`); customer audit rights live Remaining. Stage 79 D1 Commercial Data Exit fidelity Complete (MVP) — `docs/STAGE_79_FIDELITY.md` (`test_stage79_fidelity_d1.py`); maps R1–A1. Stage 79 H79x exit + freeze Complete (MVP) — `docs/STAGE_79_EXIT_CRITERIA.md`, ADR-165 (`test_stage79_exit_h79x.py`). Stage 80 open Complete (MVP) — `docs/ADR_166_STAGE80_OPEN.md`, `docs/STAGE_80_PLAN.md` (`test_stage80_open.py`). Stage 80 P1 platform dashboard charts Complete (MVP) — `/api/v1/platform/dashboard/*` (`test_platform_dashboard_charts_p1.py`); `mrr_fabricated_claimed: false` (ADR-002). Stage 80 T1 tenant role-scoped dashboards Complete (MVP) — `dashboard_views` (`test_tenant_role_dashboard_t1.py`). Stage 80 D1 Dual-Console Dashboard fidelity Complete (MVP) — `docs/STAGE_80_FIDELITY.md` (`test_stage80_fidelity_d1.py`); maps P1–T1. Stage 80 H80x exit + freeze Complete (MVP) — `docs/STAGE_80_EXIT_CRITERIA.md`, ADR-167 (`test_stage80_exit_h80x.py`). Stage 81 open Complete (MVP) — `docs/ADR_168_STAGE81_OPEN.md`, `docs/STAGE_81_PLAN.md` (`test_stage81_open.py`). Stage 81 A1 Tenant Admin RBAC console surfaces Complete (MVP) — `/users`, `/admin/roles`, `/admin/permissions` (`test_admin_console_a1.py`). Stage 81 S1 store-scoped manager ops Complete (MVP) — `store_scope` / `stores.manager_id` (`test_store_scoped_manager_s1.py`); `user_store_membership_claimed: false` (ADR-005). Stage 81 D1 Dual-Console Admin fidelity Complete (MVP) — `docs/STAGE_81_FIDELITY.md` (`test_stage81_fidelity_d1.py`); maps A1–S1. Stage 81 H81x exit + freeze Complete (MVP) — `docs/STAGE_81_EXIT_CRITERIA.md`, ADR-169 (`test_stage81_exit_h81x.py`). Stage 82 open Complete (MVP) — `docs/ADR_170_STAGE82_OPEN.md`, `docs/STAGE_82_PLAN.md` (`test_stage82_open.py`). Stage 82 C1 tenant dashboard slices Complete (MVP) — `/api/v1/dashboard/summary|sales-trend|top-products|expenses|stock-alerts|user-stats` (`test_dashboard_slices_c1.py`). Stage 82 P1 Platform Plans console Complete (MVP) — `/platform/plans` + Activity alias (`test_platform_plans_p1.py`); `mrr_fabricated_claimed: false` (ADR-002). Stage 82 D1 Dual-Console Surface Parity fidelity Complete (MVP) — `docs/STAGE_82_FIDELITY.md` (`test_stage82_fidelity_d1.py`); maps C1–P1. Stage 82 H82x exit + freeze Complete (MVP) — `docs/STAGE_82_EXIT_CRITERIA.md`, ADR-171 (`test_stage82_exit_h82x.py`). Stage 83 open Complete (MVP) — `docs/ADR_172_STAGE83_OPEN.md`, `docs/STAGE_83_PLAN.md` (`test_stage83_open.py`). Stage 83 S1 store-scoped chart depth Complete (MVP) — `store_ids` on charts/slices (`test_store_scoped_charts_s1.py`). Stage 83 U1 Tenant Admin user-ops Complete (MVP) — reset password + org assignment UI (`test_admin_user_ops_u1.py`). Stage 83 D1 Dual-Console Ops fidelity Complete (MVP) — `docs/STAGE_83_FIDELITY.md` (`test_stage83_fidelity_d1.py`); maps S1–U1. Stage 83 H83x exit + freeze Complete (MVP) — `docs/STAGE_83_EXIT_CRITERIA.md`, ADR-173 (`test_stage83_exit_h83x.py`). Stage 84 A1 dotted permission aliases Complete (MVP) — `view`→`read`; `inventory.view` / `inventory:read` (`test_permission_aliases_a1.py`). Stage 84 S1 dashboard slice depth Complete (MVP) — expenses-by-category + `/dashboard/credit` + cashier open-shift UI (`test_dashboard_slice_depth_s1.py`). Stage 84 D1 Dual-Console Permission & Slice fidelity Complete (MVP) — `docs/STAGE_84_FIDELITY.md` (`test_stage84_fidelity_d1.py`). Stage 84 H84x exit + freeze Complete (MVP) — `docs/STAGE_84_EXIT_CRITERIA.md`, ADR-175 (`test_stage84_exit_h84x.py`). Stage 85 R1 platform subscriptions roster Complete (MVP) — tenant×plan metadata (`test_platform_subscriptions_r1.py`); `subscriptions_live_claimed` remains false. Stage 85 E1 admin email password reset Complete (MVP) — `POST /users/{id}/password-reset-email` (`test_admin_email_reset_e1.py`). Stage 85 L1 org-chart role catalog Complete (MVP) — Manager/Tenant Admin labels + system matrix (`test_org_role_catalog_l1.py`). Stage 85 D1 House Roster & Tenant Access Ops fidelity Complete (MVP) — `docs/STAGE_85_FIDELITY.md` (`test_stage85_fidelity_d1.py`). Stage 85 H85x exit + freeze Complete (MVP) — `docs/STAGE_85_EXIT_CRITERIA.md`, ADR-177 (`test_stage85_exit_h85x.py`). Stage 86 P1 House tenant provision Complete (MVP) — `POST /platform/tenants` (`test_platform_tenant_provision_p1.py`). Stage 86 E1 platform email password reset Complete (MVP) — `POST /platform/users/{id}/password-reset-email` (`test_platform_email_reset_e1.py`). Stage 86 A1 platform audit Activity depth Complete (MVP) — filters + `/platform/activity` (`test_platform_audit_activity_a1.py`). Stage 86 D1 House Provision & Platform Access Ops fidelity Complete (MVP) — `docs/STAGE_86_FIDELITY.md` (`test_stage86_fidelity_d1.py`). Stage 86 H86x exit + freeze Complete (MVP) — `docs/STAGE_86_EXIT_CRITERIA.md`, ADR-179 (`test_stage86_exit_h86x.py`). Stage 87 X1 platform audit export + chain verify Complete (MVP) — `GET /platform/audit/export` / `GET /platform/audit/verify` (`test_platform_audit_integrity_x1.py`). Stage 87 Y1 House ops surface polish Complete (MVP) — health cards, last_activity UI, `PATCH /platform/tenants/{id}/notes`, settings honesty (`test_house_ops_surface_y1.py`). Stage 87 Z1 console boundary hardening Complete (MVP) — `ribdigi_principal` cookie + middleware + soft-delete honesty (`test_console_boundary_z1.py`). Stage 87 D1 House Integrity & Console Boundary Ops fidelity Complete (MVP) — `docs/STAGE_87_FIDELITY.md` (`test_stage87_fidelity_d1.py`). Stage 87 H87x exit + freeze Complete (MVP) — `docs/STAGE_87_EXIT_CRITERIA.md`, ADR-181 (`test_stage87_exit_h87x.py`). Stage 88 L1 tenant lifecycle controls Complete (MVP) — `PATCH /platform/tenants/{id}/lifecycle` + suspend reason (`test_platform_tenant_lifecycle_l1.py`). Stage 88 R1 tenant roster export + at-risk queue Complete (MVP) — `GET /platform/tenants/export` / `GET /platform/tenants/at-risk` (`test_platform_tenant_roster_r1.py`). Stage 88 S1 platform staff invite + session ops Complete (MVP) — email invite + `GET/DELETE /platform/users/sessions` (`test_platform_staff_security_s1.py`). Stage 88 D1 House Lifecycle & Staff Security Ops fidelity Complete (MVP) — `docs/STAGE_88_FIDELITY.md` (`test_stage88_fidelity_d1.py`). Stage 88 H88x exit + freeze Complete (MVP) — `docs/STAGE_88_EXIT_CRITERIA.md`, ADR-183 (`test_stage88_exit_h88x.py`). Stage 89 A1 House Tenant Admin assist Complete (MVP) — `POST /platform/tenants/{id}/admin/password-reset-email` / `…/admin/resend-verification` (`test_platform_tenant_admin_assist_a1.py`). Stage 89 F1 roster filters + dashboard at-risk KPIs Complete (MVP) — `plan_code`/`industry` filters + `at_risk_count` (`test_platform_roster_intel_f1.py`). Stage 89 C1 plan catalog + billing roster depth Complete (MVP) — metadata catalog + trial_ends deep-links (`test_platform_catalog_billing_c1.py`). Stage 89 D1 House Customer Assist & Roster Intelligence Ops fidelity Complete (MVP) — `docs/STAGE_89_FIDELITY.md` (`test_stage89_fidelity_d1.py`). Stage 89 H89x exit + freeze Complete (MVP) — `docs/STAGE_89_EXIT_CRITERIA.md`, ADR-185 (`test_stage89_exit_h89x.py`). Stage 90 E1 House email delivery visibility Complete (MVP) — `platform.email.delivery` audit + `delivery_only` (`test_platform_email_delivery_visibility_e1.py`). Stage 90 O1 operator surfaces Complete (MVP) — Health contacts/security + Settings runbook links (`test_house_operator_surfaces_o1.py`). Stage 90 Q1 roster findability + plan context Complete (MVP) — admin email search + detail soft limits (`test_platform_roster_findability_q1.py`). Stage 90 D1 House Operator Visibility & Delivery Ops fidelity Complete (MVP) — `docs/STAGE_90_FIDELITY.md` (`test_stage90_fidelity_d1.py`). Stage 90 H90x exit + freeze Complete (MVP) — `docs/STAGE_90_EXIT_CRITERIA.md`, ADR-187 (`test_stage90_exit_h90x.py`). Stage 91 I1 Audit/Activity date-range investigation Complete (MVP) — `test_platform_audit_investigation_i1.py`. Stage 91 N1 dashboard→roster deep-links + tenant last House email delivery Complete (MVP) — `test_platform_nav_delivery_n1.py`. Stage 91 P1 staff presence / health required / House TZ / `GET /platform/evidence` Complete (MVP) — `test_house_posture_evidence_p1.py`. Stage 91 D1 House Operator Investigation & Evidence Ops fidelity Complete (MVP) — `docs/STAGE_91_FIDELITY.md` (`test_stage91_fidelity_d1.py`). Stage 91 H91x exit + freeze Complete (MVP) — `docs/STAGE_91_EXIT_CRITERIA.md`, ADR-189 (`test_stage91_exit_h91x.py`). Stage 92 B1 Investigation export + evidence download Complete (MVP) — `test_stage92_console_workflow_b1.py`. Stage 92 G1 roster triage + commercial-metadata context Complete (MVP) — `test_stage92_roster_context_g1.py`. Stage 92 K1 House regional formats + runtime evidence detail Complete (MVP) — `test_stage92_readiness_formats_k1.py`. Stage 92 D1 House Console Workflow & Readiness Ops fidelity Complete (MVP) — `docs/STAGE_92_FIDELITY.md` (`test_stage92_fidelity_d1.py`). Stage 92 H92x exit + freeze Complete (MVP) — `docs/STAGE_92_EXIT_CRITERIA.md`, ADR-191 (`test_stage92_exit_h92x.py`). Stage 93 M1 Roster navigation & export Complete (MVP) — `test_stage93_roster_navigation_m1.py`. Stage 93 J1 Staff delivery & integrity Complete (MVP) — `test_stage93_staff_integrity_j1.py`. Stage 93 V1 Format, evidence & runtime posture Complete (MVP) — `test_stage93_runtime_posture_v1.py`. Stage 93 D1 House Navigation & Runtime Ops fidelity Complete (MVP) — `docs/STAGE_93_FIDELITY.md` (`test_stage93_fidelity_d1.py`). Stage 93 H93x exit + freeze Complete (MVP) — `docs/STAGE_93_EXIT_CRITERIA.md`, ADR-193 (`test_stage93_exit_h93x.py`). Stage 94 open Complete (MVP) — `docs/STAGE_94_PLAN.md`, ADR-194 (`test_stage94_open.py`). Stage 94 W1 Platform staff discovery Complete (MVP) — `test_stage94_staff_discovery_w1.py`. Stage 94 H1 Configuration integrity & release identity Complete (MVP) — `test_stage94_configuration_integrity_h1.py` (`runtime_identity`). Stage 94 T2 Console state & queue awareness Complete (MVP) — `test_stage94_console_state_t2.py`. Stage 94 D1 House Discovery & Runtime Assurance Ops fidelity Complete (MVP) — `docs/STAGE_94_FIDELITY.md` (`test_stage94_fidelity_d1.py`). Stage 94 H94x exit + freeze Complete (MVP) — `docs/STAGE_94_EXIT_CRITERIA.md`, ADR-195 (`test_stage94_exit_h94x.py`). Stage 95 open Complete (MVP) — `docs/STAGE_95_PLAN.md`, ADR-196 (`test_stage95_open.py`). Stage 95 N1 Tenant Shell IA regrouping Complete (MVP) — `test_stage95_shell_ia_n1.py`. Stage 95 P1 Party & stock discoverability Complete (MVP) — `test_stage95_party_stock_p1.py`. Stage 95 C1 Chrome & settings alias fidelity Complete (MVP) — `test_stage95_chrome_c1.py`. Stage 95 D1 Tenant MVP Navigation Ops fidelity Complete (MVP) — `docs/STAGE_95_FIDELITY.md` (`test_stage95_fidelity_d1.py`). Stage 95 H95x exit + freeze Complete (MVP) — `docs/STAGE_95_EXIT_CRITERIA.md`, ADR-197 (`test_stage95_exit_h95x.py`). Stage 96 open Complete (MVP) — `docs/STAGE_96_PLAN.md`, ADR-198 (`test_stage96_open.py`). Stage 96 B1 Dashboard Business Overview fidelity Complete (MVP) — `test_stage96_dashboard_overview_b1.py`. Stage 96 G1 Global topbar search Complete (MVP) — `test_stage96_global_search_g1.py` (`GET /search`). Stage 96 L1 Finance / Sales / Settings leaf fidelity Complete (MVP) — `test_stage96_leaf_fidelity_l1.py`. Stage 96 D1 Tenant MVP Outline Surface Fidelity Ops fidelity Complete (MVP) — `docs/STAGE_96_FIDELITY.md` (`test_stage96_fidelity_d1.py`). Stage 96 H96x exit + freeze Complete (MVP) — `docs/STAGE_96_EXIT_CRITERIA.md`, ADR-199 (`test_stage96_exit_h96x.py`).  Stages 1–42 frozen for Stage 42 scope; external LLM / AI certification Remaining. — `docs/STAGE_42_FIDELITY.md` (`test_stage42_fidelity_d1.py`); maps A1–P1; `ai_certification_claimed` / `external_llm_claimed` remain false; external LLM / AI certification Remaining. — `docs/AI_PROVIDER_BOUNDARY_MVP.md`, `ops/mvp/ai-provider-boundary.json` (`test_ai_provider_boundary_p1.py`); external LLM Remaining. — `docs/AI_USE_DISCLOSURE_MVP.md`, `ops/mvp/ai-use-disclosure.json` (`test_ai_use_disclosure_a1.py`); AI certification Remaining.; Stages 1–41 frozen for Stage 41 scope; WCAG AA audit / public change calendar Remaining. — `docs/STAGE_41_FIDELITY.md` (`test_stage41_fidelity_d1.py`); maps A1–C1; `wcag_aa_claimed` / `change_calendar_live` remain false; WCAG AA audit / public change calendar Remaining. — `docs/CHANGE_GOVERNANCE_MVP.md`, `ops/mvp/change-governance.json` (`test_change_governance_c1.py`); public change calendar Remaining. — `docs/ACCESSIBILITY_STATEMENT_MVP.md`, `ops/mvp/accessibility-statement.json` (`test_accessibility_statement_a1.py`); WCAG AA audit Remaining.; Stages 1–40 frozen for Stage 40 scope; live status page / SBOM pipeline Remaining. — `docs/STAGE_40_FIDELITY.md` (`test_stage40_fidelity_d1.py`); maps U1–S1; `status_page_live` / `sbom_pipeline_live` remain false; live status page / SBOM pipeline Remaining. — `docs/SBOM_DISCLOSURE_MVP.md`, `ops/mvp/sbom-disclosure.json` (`test_sbom_disclosure_s1.py`); live SBOM pipeline Remaining.`, ADR-084 (`test_stage39_exit_h39x.py`). Stage 32 H32x exit + freeze: `docs/STAGE_32_EXIT_CRITERIA.md`, ADR-070 (`test_stage32_exit_h32x.py`). Stage 28 H28x exit + freeze: `docs/STAGE_28_EXIT_CRITERIA.md`, ADR-062 (`test_stage28_exit_h28x.py`).



### 10.1 Horizontal Scaling

**Backend API:**
- Scale based on CPU (70%) and request latency (p95 > 500ms)
- Min: 5 pods, Max: 20 pods
- Pod disruption budget: minAvailable: 3

**Frontend:**
- Scale based on CPU (80%)
- Min: 3 pods, Max: 10 pods

**Celery Workers:**
- Scale based on queue depth
- Min: 3 pods, Max: 15 pods
- Use KEDA (Kubernetes Event-Driven Autoscaling) for queue-based scaling

### 10.2 Database High Availability

**PostgreSQL:**
- Primary-Replica setup with streaming replication
- Automatic failover using Patroni or cloud-managed solution
- Read replicas for report generation and analytics
- Connection pooling via PgBouncer — Stage 27 P1 MVP packaging (`docs/PGBOUNCER_MVP.md` (Stage 29 B2 soak pack: `docs/PGBOUNCER_SOAK_PACK_MVP.md`, `test_pgbouncer_soak_b2.py`), `ops/postgres/pgbouncer.ini.example`, `test_pgbouncer_p1.py`); optional compose overlay; not default CI / in-cluster Helm claim. Stage 27 D1 locks release evidence (`docs/STAGE_27_FIDELITY.md`, `test_stage27_fidelity_d1.py`) across B1–L1. Stage 27 H27x exit + freeze: `docs/STAGE_27_EXIT_CRITERIA.md`, ADR-060 (`test_stage27_exit_h27x.py`).

**Redis:**
- Redis Sentinel for high availability
- Read replicas for cache reads
- Persistent storage for session data (AOF + RDB)

### 10.3 Multi-Region Deployment (Future)

| Region | Role | RTO | RPO |
|--------|------|-----|-----|
| us-east-1 | Primary | — | — |
| us-west-2 | Standby | 4 hours | 15 minutes |
| eu-west-1 | Read Replica | 8 hours | 1 hour |

---

## 11. Backup & Disaster Recovery

**MVP fidelity:** Logical `.ribbak` DR is Complete (`docs/DR_LOGICAL_BACKUP_RUNBOOK.md`, Stage 23 B1). Stage 26 W1 documents WAL archiving → S3-compatible offsite + `.ribbak` mirror scripts (`docs/DR_WAL_PITR_RUNBOOK.md`, `ops/postgres/`, `ops/backup/`, `test_wal_pitr_w1.py`). Operator staging PITR drill execution and managed-cloud automation remain Remaining — do not treat the aspirational schedule below as CI-certified.

### 11.1 Backup Schedule

| Component | Frequency | Retention | Method |
|-----------|-----------|-----------|--------|
| PostgreSQL | Daily + Continuous WAL | 30 days | pg_basebackup + WAL archiving |
| Redis | Every 6 hours | 7 days | RDB snapshots + AOF |
| S3 Objects | Continuous versioning | 90 days | Cross-region replication |
| Config/Secrets | On change | 30 versions | Git + Vault versioning |

### 11.2 Disaster Recovery Procedures

**Scenario 1: Database Corruption**
1. Stop application writes
2. Restore from latest clean backup to new instance
3. Replay WAL to point just before corruption
4. Verify data integrity
5. Update connection strings
6. Resume operations

**Scenario 2: Complete Region Failure**
1. Activate standby region
2. Promote read replica to primary
3. Update DNS to point to standby
4. Verify all services operational
5. Communicate with tenants
6. Initiate failback when primary recovers

**Scenario 3: Ransomware Attack**
1. Isolate affected systems
2. Revoke all active sessions
3. Restore from pre-attack backups (verified clean)
4. Rotate all secrets and credentials
5. Patch vulnerability
6. Verify no persistence mechanisms remain

### 11.3 Recovery Objectives

| Environment | RTO | RPO |
|-------------|-----|-----|
| Development | 24 hours | 24 hours |
| Staging | 4 hours | 1 hour |
| Production | 1 hour | 15 minutes |

---

## 12. Security Hardening

### 12.1 Container Hardening

- Run as non-root user (UID 1000+)
- Read-only root filesystem
- Drop all Linux capabilities
- No privileged containers
- Resource limits enforced
- Image scanning before deployment (Trivy)

### 12.2 Network Hardening

- Default-deny network policies
- TLS 1.3 only for external communication
- mTLS for internal service communication (Istio/Linkerd)
- Bastion host for administrative access
- VPN required for production cluster access

### 12.3 Secret Management

- Kubernetes Secrets or External Secrets Operator
- HashiCorp Vault for dynamic secrets
- Automatic secret rotation every 90 days
- No secrets in environment variables for local development
- Sealed Secrets for GitOps workflows

---

## 13. Troubleshooting

### 13.1 Common Issues

**Pod CrashLoopBackOff:**
```bash
# Check logs
kubectl logs -n ribdigi-production deployment/ribdigi-backend --previous

# Check events
kubectl get events -n ribdigi-production --sort-by='.lastTimestamp'

# Check resource limits
kubectl describe pod -n ribdigi-production <pod-name>
```

**Database Connection Issues:**
```bash
# Check connection pool status
# Prefer: confirm DATABASE_URL targets pgbouncer:6432 and `SHOW POOLS;` inside PgBouncer admin console
# (Stage 27 P1 — no fake check_pool() helper). See docs/PGBOUNCER_MVP.md.

# Check PostgreSQL logs
kubectl logs -n ribdigi-production statefulset/postgres
```

**High Memory Usage:**
```bash
# Check memory profiling
kubectl exec -it -n ribdigi-production <backend-pod> -- python -m memory_profiler app/main.py

# Check for memory leaks in Celery
kubectl logs -n ribdigi-production deployment/ribdigi-celery-worker | grep "Memory"
```

**Migration Failures:**
```bash
# Check migration status
kubectl logs -n ribdigi-production job/db-migration-job

# Manual rollback
kubectl exec -it -n ribdigi-production <backend-pod> -- alembic downgrade -1
```

### 13.2 Debug Commands

```bash
# Port forward to database
kubectl port-forward -n ribdigi-production svc/postgres 5432:5432

# Port forward to Redis
kubectl port-forward -n ribdigi-production svc/redis 6379:6379

# Execute shell in pod
kubectl exec -it -n ribdigi-production <pod-name> -- /bin/sh

# Check resource usage
kubectl top pods -n ribdigi-production

# Check ingress status
kubectl describe ingress -n ribdigi-production
```

---

## 14. Appendix: Resource Requirements

### 14.1 Production Resource Estimates

**Per Tenant (Average):**
- Database storage: 5 GB
- File storage: 2 GB
- Memory (active): 50 MB

**Total Production Cluster (1000 tenants):**

| Component | Instances | CPU (cores) | Memory (GB) | Storage (GB) |
|-----------|-----------|-------------|-------------|--------------|
| Backend API | 5–20 | 10–40 | 10–40 | — |
| Frontend | 3–10 | 3–10 | 3–10 | — |
| Celery Workers | 3–15 | 3–15 | 6–30 | — |
| PostgreSQL | 2 (HA) | 4 | 16 | 500 |
| Redis | 3 (Sentinel) | 2 | 8 | 50 |
| RabbitMQ | 3 (Cluster) | 3 | 6 | 100 |
| Monitoring | 3 | 2 | 8 | 200 |
| **Total** | | **27–94** | **51–124** | **850** |

### 14.2 Cost Optimization

- Use spot instances for Celery workers (fault-tolerant)
- Right-size pods based on actual usage metrics
- Implement auto-scaling down to minimum during off-peak hours
- Use reserved instances for database and Redis
- Archive old tenant data to cold storage

---

**Document Version:** 1.0.0  
**Compatible With:** RIBDIGI ERP MVP (Version 1.0)  
**Technical Stack:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Redis, Celery + RabbitMQ, React/Next.js, Docker, Kubernetes, GitHub Actions  
**Owner:** DevOps & Platform Engineering Team  
**Review Cycle:** Monthly or upon infrastructure changes

Stage 97 D1 module leaf honesty fidelity — `docs/STAGE_97_FIDELITY.md` (`test_stage97_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 98 D1 ops queue honesty fidelity — `docs/STAGE_98_FIDELITY.md` (`test_stage98_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 99 D1 document pipeline honesty fidelity — `docs/STAGE_99_FIDELITY.md` (`test_stage99_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 100 D1 reports & ledger discovery fidelity — `docs/STAGE_100_FIDELITY.md` (`test_stage100_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 101 D1 inventory ops & shift history fidelity — `docs/STAGE_101_FIDELITY.md` (`test_stage101_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 102 D1 residual reports & surface honesty fidelity — `docs/STAGE_102_FIDELITY.md` (`test_stage102_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 103 D1 security, backup & company org fidelity — `docs/STAGE_103_FIDELITY.md` (`test_stage103_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 104 D1 ledger filters, commerce leaves & admin fidelity — `docs/STAGE_104_FIDELITY.md` (`test_stage104_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 105 D1 permissions, store policies & platform audit fidelity — `docs/STAGE_105_FIDELITY.md` (`test_stage105_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 106 D1 approval filters, company profile & notification inbox fidelity — `docs/STAGE_106_FIDELITY.md` (`test_stage106_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 107 D1 POS sections, commerce filters & ops leaves fidelity — `docs/STAGE_107_FIDELITY.md` (`test_stage107_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 108 D1 AI analysis leaves, credit statement & users directory fidelity — `docs/STAGE_108_FIDELITY.md` (`test_stage108_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 109 D1 report filters, document status leaves & platform status fidelity — `docs/STAGE_109_FIDELITY.md` (`test_stage109_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 110 D1 purchasing status leaves, expense decision queue & admin audit fidelity — `docs/STAGE_110_FIDELITY.md` (`test_stage110_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 111 D1 inventory movement types, posted sales returns & cheque hash fidelity — `docs/STAGE_111_FIDELITY.md` (`test_stage111_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 112 D1 report schedule leaves, stores cash drawer & platform plan fidelity — `docs/STAGE_112_FIDELITY.md` (`test_stage112_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 113 D1 notification read, cheque exceptions & fulfillment status fidelity — `docs/STAGE_113_FIDELITY.md` (`test_stage113_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 114 D1 residual status & ops filter discoverability fidelity — `docs/STAGE_114_FIDELITY.md` (`test_stage114_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 115 D1 notification history honesty & residual filter discoverability fidelity — `docs/STAGE_115_FIDELITY.md` (`test_stage115_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 116 D1 officer roles, exact invoices & residual audit fidelity — `docs/STAGE_116_FIDELITY.md` (`test_stage116_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 117 D1 permissions role, platform audit & stretch audit fidelity — `docs/STAGE_117_FIDELITY.md` (`test_stage117_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 118 D1 fiscal close, inactive customers & catalog export fidelity — `docs/STAGE_118_FIDELITY.md` (`test_stage118_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1). Alembic `20260812_0090` adds `fiscal_closed_period_starts`.
Stage 119 D1 inactive suppliers, party export & print preview fidelity — `docs/STAGE_119_FIDELITY.md` (`test_stage119_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 120 D1 inactive products, users & expenses export fidelity — `docs/STAGE_120_FIDELITY.md` (`test_stage120_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 121 D1 inactive stores, warehouses & location export fidelity — `docs/STAGE_121_FIDELITY.md` (`test_stage121_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 122 D1 inactive org units, catalog meta & export fidelity — `docs/STAGE_122_FIDELITY.md` (`test_stage122_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 123 D1 inactive finance masters, customer groups & export fidelity — `docs/STAGE_123_FIDELITY.md` (`test_stage123_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 124 D1 inactive product variants, custom roles & export fidelity — `docs/STAGE_124_FIDELITY.md` (`test_stage124_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 125 D1 inactive liquid accounts, recurring expenses & export fidelity — `docs/STAGE_125_FIDELITY.md` (`test_stage125_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 126 D1 inactive bank connections, paused webhooks & export fidelity — `docs/STAGE_126_FIDELITY.md` (`test_stage126_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 127 D1 API-key status, FX rates & report-schedule export fidelity — `docs/STAGE_127_FIDELITY.md` (`test_stage127_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 128 D1 session status, passkey inventory & document-settings export fidelity — `docs/STAGE_128_FIDELITY.md` (`test_stage128_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 129 D1 admin session inventory, notifications & backup-job export fidelity — `docs/STAGE_129_FIDELITY.md` (`test_stage129_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 130 D1 cheque, POS session & stock-count list export fidelity — `docs/STAGE_130_FIDELITY.md` (`test_stage130_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 131 D1 journal entry, bank statement & email-settings export fidelity — `docs/STAGE_131_FIDELITY.md` (`test_stage131_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 132 D1 sales invoice, stock-transfer & purchase invoice register export fidelity — `docs/STAGE_132_FIDELITY.md` (`test_stage132_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 133 D1 sales quotation, order & return register export fidelity — `docs/STAGE_133_FIDELITY.md` (`test_stage133_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 134 D1 purchase request, purchase order & GRN register export fidelity — `docs/STAGE_134_FIDELITY.md` (`test_stage134_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 135 D1 purchase return, SMS settings & stores transfer export fidelity — `docs/STAGE_135_FIDELITY.md` (`test_stage135_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 136 D1 customer payment, supplier payment & credit aging export fidelity — `docs/STAGE_136_FIDELITY.md` (`test_stage136_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 137 D1 stock movements, low-stock alert & expiring batches export fidelity — `docs/STAGE_137_FIDELITY.md` (`test_stage137_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 138 D1 early-pay settings, expense approval settings & purchasing approval settings export fidelity — `docs/STAGE_138_FIDELITY.md` (`test_stage138_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 139 D1 expense budgets, account transactions & fiscal period export fidelity — `docs/STAGE_139_FIDELITY.md` (`test_stage139_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 140 D1 storage settings, notification preferences & backup settings export fidelity — `docs/STAGE_140_FIDELITY.md` (`test_stage140_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 141 D1 outstanding bills, supplier payment schedule & party statement export fidelity — `docs/STAGE_141_FIDELITY.md` (`test_stage141_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 142 D1 POS sales register, session Z-report & store cash drawer settings export fidelity — `docs/STAGE_142_FIDELITY.md` (`test_stage142_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 143 D1 company profile, jobs catalog & onboarding checklist export fidelity — `docs/STAGE_143_FIDELITY.md` (`test_stage143_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 144 D1 webhook deliveries, inventory FEFO settings & audit archives export fidelity — `docs/STAGE_144_FIDELITY.md` (`test_stage144_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 145 D1 AI security alerts, report templates & business insights export fidelity — `docs/STAGE_145_FIDELITY.md` (`test_stage145_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 146 D1 AI low-stock prediction, demand forecast & dead-stock export fidelity — `docs/STAGE_146_FIDELITY.md` (`test_stage146_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 147 D1 AI sales analysis, expense analysis & purchases analysis export fidelity — `docs/STAGE_147_FIDELITY.md` (`test_stage147_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 148 D1 AI chat history, customer insights & cross-domain analysis export fidelity — `docs/STAGE_148_FIDELITY.md` (`test_stage148_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 149 D1 AI document analyze, platform staff users & platform staff sessions export fidelity — `docs/STAGE_149_FIDELITY.md` (`test_stage149_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 150 D1 platform plans catalog, subscriptions roster & house settings export fidelity — `docs/STAGE_150_FIDELITY.md` (`test_stage150_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 151 D1 platform health checks, operator evidence & at-risk tenants export fidelity — `docs/STAGE_151_FIDELITY.md` (`test_stage151_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 152 D1 platform dashboard aggregates, industries catalog & admin permissions matrix export fidelity — `docs/STAGE_152_FIDELITY.md` (`test_stage152_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 153 D1 tenant dashboard aggregates, customer history & supplier history export fidelity — `docs/STAGE_153_FIDELITY.md` (`test_stage153_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 154 D1 PO amendments, product batches & API-key usage export fidelity — `docs/STAGE_154_FIDELITY.md` (`test_stage154_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 155 D1 store inventory, store sales & product warehouse-stock export fidelity — `docs/STAGE_155_FIDELITY.md` (`test_stage155_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 156 D1 product images, per-product variants & bank-feed settings export fidelity — `docs/STAGE_156_FIDELITY.md` (`test_stage156_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 157 D1 AI inventory predictions, dashboard sales-trend & top-products export fidelity — `docs/STAGE_157_FIDELITY.md` (`test_stage157_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 158 D1 dashboard stock-alerts, expenses & credit export fidelity — `docs/STAGE_158_FIDELITY.md` (`test_stage158_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 159 D1 dashboard user-stats, summary & accounting trial-balance export fidelity — `docs/STAGE_159_FIDELITY.md` (`test_stage159_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 160 D1 accounting profit-loss, reports cash-flow & balance-sheet path export fidelity — `docs/STAGE_160_FIDELITY.md` (`test_stage160_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 161 D1 reports profit-loss, trial-balance & tax path export fidelity — `docs/STAGE_161_FIDELITY.md` (`test_stage161_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 162 D1 approved navigation hierarchy fidelity — `docs/STAGE_162_FIDELITY.md` (`test_stage162_fidelity_d1.py`); main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 163 D1 offline foundation fidelity — `docs/STAGE_163_FIDELITY.md` (`test_stage163_fidelity_d1.py`); Alembic `20260813_0091` adds `offline_devices`; PWA static assets under `frontend/public/`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 164 D1 sync queue fidelity — `docs/STAGE_164_FIDELITY.md` (`test_stage164_fidelity_d1.py`); Alembic `20260813_0092` adds `sync_queue_items`, `sync_conflicts`, `transactions.client_request_id`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 165 D1 offline client queue fidelity — `docs/STAGE_165_FIDELITY.md` (`test_stage165_fidelity_d1.py`); Alembic `20260813_0093` adds `pos_held_carts`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 166 D1 Offline Complete Hardening fidelity — `docs/STAGE_166_FIDELITY.md` (`test_stage166_fidelity_d1.py`); Alembic `20260813_0094` adds `pos_held_carts.stock_reserved` / `reservation_lines`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 167 D1 Offline Complete E2E Hardening fidelity — `docs/STAGE_167_FIDELITY.md` (`test_stage167_fidelity_d1.py`); Alembic `20260813_0095` adds `pos_held_carts.expires_at`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 168 D1 Offline Complete Attestation fidelity — `docs/STAGE_168_FIDELITY.md` (`test_stage168_fidelity_d1.py`); SW cache `ribdigi-static-v168`; attestation `docs/OFFLINE_COMPLETE_ATTESTATION.md` / `ops/mvp/offline-complete-attestation.json`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 169 D1 Production Ops Hardening fidelity — `docs/STAGE_169_FIDELITY.md` (`test_stage169_fidelity_d1.py`); migration gate `docs/MIGRATION_GATE_MVP.md` / `ops/mvp/migration-gate.json` (single Alembic head proof in pytest); backup drill honesty `docs/BACKUP_RESTORE_DRILL_HONESTY_MVP.md`; offline/sync runbook `docs/OFFLINE_SYNC_RUNBOOK_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).

Stage 170 D1 Support Readiness fidelity — `docs/STAGE_170_FIDELITY.md` (`test_stage170_fidelity_d1.py`); `docs/SUPPORT_READINESS_MVP.md` / `docs/INCIDENT_SEVERITY_MATRIX_MVP.md` / `docs/OFFLINE_SYNC_ESCALATION_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 171 D1 Knowledge Base fidelity — `docs/STAGE_171_FIDELITY.md` (`test_stage171_fidelity_d1.py`); `docs/KNOWLEDGE_BASE_MVP.md` / `docs/FAQ_OFFLINE_POS_MVP.md` / `docs/TROUBLESHOOTING_INDEX_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 172 D1 Cashier Quickstart fidelity — `docs/STAGE_172_FIDELITY.md` (`test_stage172_fidelity_d1.py`); `docs/CASHIER_QUICKSTART_MVP.md` / `docs/CASHIER_BIND_CATALOG_MVP.md` / `docs/CASHIER_POS_DAYONE_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 173 D1 Store-Open Checklist fidelity — `docs/STAGE_173_FIDELITY.md` (`test_stage173_fidelity_d1.py`); `docs/STORE_OPEN_CHECKLIST_MVP.md` / `docs/STORE_OPEN_LOWSTOCK_MVP.md` / `docs/STORE_OPEN_HEALTH_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 174 D1 Store-Close Checklist fidelity — `docs/STAGE_174_FIDELITY.md` (`test_stage174_fidelity_d1.py`); `docs/STORE_CLOSE_CHECKLIST_MVP.md` / `docs/STORE_CLOSE_DRAIN_MVP.md` / `docs/STORE_CLOSE_TRIAGE_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 175 D1 Shift-Handover Checklist fidelity — `docs/STAGE_175_FIDELITY.md` (`test_stage175_fidelity_d1.py`); `docs/SHIFT_HANDOVER_CHECKLIST_MVP.md` / `docs/SHIFT_HANDOVER_SNAPSHOT_MVP.md` / `docs/SHIFT_HANDOVER_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 176 D1 Weekly POS Ops Review fidelity — `docs/STAGE_176_FIDELITY.md` (`test_stage176_fidelity_d1.py`); `docs/WEEKLY_POS_OPS_REVIEW_MVP.md` / `docs/WEEKLY_POS_OPS_ADHERENCE_MVP.md` / `docs/WEEKLY_POS_OPS_SIGNALS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 177 D1 Monthly POS Ops fidelity — `docs/STAGE_177_FIDELITY.md` (`test_stage177_fidelity_d1.py`); `docs/MONTHLY_POS_OPS_REVIEW_MVP.md` / `docs/MONTHLY_POS_OPS_TRENDS_MVP.md` / `docs/MONTHLY_POS_OPS_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 178 D1 Quarterly POS Ops fidelity — `docs/STAGE_178_FIDELITY.md` (`test_stage178_fidelity_d1.py`); `docs/QUARTERLY_POS_OPS_REVIEW_MVP.md` / `docs/QUARTERLY_POS_OPS_ROLLUP_MVP.md` / `docs/QUARTERLY_POS_OPS_GATES_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 179 D1 Offline Complete Remaining-Gate Index fidelity — `docs/STAGE_179_FIDELITY.md` (`test_stage179_fidelity_d1.py`); `docs/OFFLINE_COMPLETE_REMAINING_GATE_MVP.md` / `docs/OFFLINE_COMPLETE_BLOCKERS_MVP.md` / `docs/OFFLINE_COMPLETE_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 180 D1 Go-Live Remaining-Gate Index fidelity — `docs/STAGE_180_FIDELITY.md` (`test_stage180_fidelity_d1.py`); `docs/GOLIVE_REMAINING_GATE_MVP.md` / `docs/GOLIVE_BLOCKERS_MVP.md` / `docs/GOLIVE_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 181 D1 Billing Remaining-Gate Index fidelity — `docs/STAGE_181_FIDELITY.md` (`test_stage181_fidelity_d1.py`); `docs/BILLING_REMAINING_GATE_MVP.md` / `docs/BILLING_BLOCKERS_MVP.md` / `docs/BILLING_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 182 D1 Membership Remaining-Gate Index fidelity — `docs/STAGE_182_FIDELITY.md` (`test_stage182_fidelity_d1.py`); `docs/MEMBERSHIP_REMAINING_GATE_MVP.md` / `docs/MEMBERSHIP_BLOCKERS_MVP.md` / `docs/MEMBERSHIP_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 183 D1 Hard-Delete Remaining-Gate Index fidelity — `docs/STAGE_183_FIDELITY.md` (`test_stage183_fidelity_d1.py`); `docs/HARD_DELETE_REMAINING_GATE_MVP.md` / `docs/HARD_DELETE_BLOCKERS_MVP.md` / `docs/HARD_DELETE_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 184 D1 Language/i18n Remaining-Gate Index fidelity — `docs/STAGE_184_FIDELITY.md` (`test_stage184_fidelity_d1.py`); `docs/I18N_REMAINING_GATE_MVP.md` / `docs/I18N_BLOCKERS_MVP.md` / `docs/I18N_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 185 D1 Schema-Per-Tenant Remaining-Gate Index fidelity — `docs/STAGE_185_FIDELITY.md` (`test_stage185_fidelity_d1.py`); `docs/SCHEMA_PER_TENANT_REMAINING_GATE_MVP.md` / `docs/SCHEMA_PER_TENANT_BLOCKERS_MVP.md` / `docs/SCHEMA_PER_TENANT_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 186 D1 Audit-Retention Remaining-Gate Index fidelity — `docs/STAGE_186_FIDELITY.md` (`test_stage186_fidelity_d1.py`); `docs/AUDIT_RETENTION_REMAINING_GATE_MVP.md` / `docs/AUDIT_RETENTION_BLOCKERS_MVP.md` / `docs/AUDIT_RETENTION_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 187 D1 Attestation Remaining-Gate Index fidelity — `docs/STAGE_187_FIDELITY.md` (`test_stage187_fidelity_d1.py`); `docs/ATTESTATION_REMAINING_GATE_MVP.md` / `docs/ATTESTATION_BLOCKERS_MVP.md` / `docs/ATTESTATION_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 188 D1 Support-SLA Remaining-Gate Index fidelity — `docs/STAGE_188_FIDELITY.md` (`test_stage188_fidelity_d1.py`); `docs/SUPPORT_SLA_REMAINING_GATE_MVP.md` / `docs/SUPPORT_SLA_BLOCKERS_MVP.md` / `docs/SUPPORT_SLA_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 189 D1 Live-Training Remaining-Gate Index fidelity — `docs/STAGE_189_FIDELITY.md` (`test_stage189_fidelity_d1.py`); `docs/LIVE_TRAINING_REMAINING_GATE_MVP.md` / `docs/LIVE_TRAINING_BLOCKERS_MVP.md` / `docs/LIVE_TRAINING_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 190 D1 Offline Materials Remaining-Gate Index fidelity — `docs/STAGE_190_FIDELITY.md` (`test_stage190_fidelity_d1.py`); `docs/OFFLINE_MATERIALS_REMAINING_GATE_MVP.md` / `docs/OFFLINE_MATERIALS_BLOCKERS_MVP.md` / `docs/OFFLINE_MATERIALS_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
Stage 191 D1 Hosted FAQ SaaS Remaining-Gate Index fidelity — `docs/STAGE_191_FIDELITY.md` (`test_stage191_fidelity_d1.py`); `docs/HOSTED_FAQ_SAAS_REMAINING_GATE_MVP.md` / `docs/HOSTED_FAQ_SAAS_BLOCKERS_MVP.md` / `docs/HOSTED_FAQ_SAAS_PACK_POINTERS_MVP.md`; main `ci.yml` remains deploy-free (Stage 18 C1).
