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

**MVP load fidelity (Stage 26 C1):** CI smoke + CI capacity profiles via `backend/loadtest/` (`--smoke`, `--ci-capacity`); evidence `/opt/cursor/artifacts/loadtest/stage26_c1_capacity_evidence.json` (`test_load_capacity_c1.py`). Authoritative doc: `docs/LOAD_CAPACITY_MVP.md`. Stage 28 C1 operator ~1000-VU cert pack: `docs/LOAD_CERT_PACK_MVP.md`, `ops/loadtest/` (`test_load_cert_pack_c1.py`) — packaging only. Operator staging ~1000-VU **execution** remains Remaining. Stage 26 D1 locks the ops platform evidence chain (`docs/STAGE_26_FIDELITY.md`, `backend/tests/test_stage26_fidelity_d1.py`) across monitoring, WAL/PITR, Kubernetes/Helm, and load capacity; main `ci.yml` remains deploy-free (Stage 18 C1). Stage 26 H26x exit + freeze: `docs/STAGE_26_EXIT_CRITERIA.md`, ADR-058 (`test_stage26_exit_h26x.py`). Stage 28 D1 staging certification fidelity: `docs/STAGE_28_FIDELITY.md` (`test_stage28_fidelity_d1.py`) maps R1–C1 packs. Stage 29 D1 operator hardening & cutover fidelity: `docs/STAGE_29_FIDELITY.md` (`test_stage29_fidelity_d1.py`) maps V1–X1 packs. Stage 29 H29x exit + freeze: `docs/STAGE_29_EXIT_CRITERIA.md`, ADR-064 (`test_stage29_exit_h29x.py`). Stage 30 L1 evidence ledger: `docs/EVIDENCE_LEDGER_MVP.md` (`test_evidence_ledger_l1.py`). Stage 30 D1 go-live support fidelity: `docs/STAGE_30_FIDELITY.md` (`test_stage30_fidelity_d1.py`) maps L1–A1 packs. Stage 30 H30x exit + freeze: `docs/STAGE_30_EXIT_CRITERIA.md`, ADR-066 (`test_stage30_exit_h30x.py`). Stage 31 D1 commercial MVP closeout fidelity: `docs/STAGE_31_FIDELITY.md` (`test_stage31_fidelity_d1.py`) maps G1–C1 packs (`docs/MVP_GATE_MATRIX_MVP.md`, `docs/MVP_DECLARATION_MVP.md`, `docs/OPERATOR_REMAINING_MVP.md`); packaging only — no go-live signed claim. Stage 31 H31x exit + freeze: `docs/STAGE_31_EXIT_CRITERIA.md`, ADR-068 (`test_stage31_exit_h31x.py`). Stage 32 D1 commercial MVP handoff fidelity: `docs/STAGE_32_FIDELITY.md` (`test_stage32_fidelity_d1.py`) maps A1–B1 packs (`docs/ACCEPTANCE_ARCHIVE_MVP.md`, `docs/OPERATOR_HANDOFF_MVP.md`, `docs/RELEASE_NOTES_MVP.md`, `docs/POST_MVP_BACKLOG_MVP.md`); packaging only — no go-live signed claim. Stage 33 D1 commercial MVP continuity fidelity: `docs/STAGE_33_FIDELITY.md` (`test_stage33_fidelity_d1.py`) maps K1–T1 packs (`docs/RESIDUAL_RISK_MVP.md`, `docs/COMPLIANCE_READINESS_MVP.md`, `docs/FIRST_TENANT_ONBOARDING_MVP.md`, `docs/KNOWLEDGE_TRANSFER_MVP.md`); packaging only — no go-live signed claim. Stage 33 H33x exit + freeze: `docs/STAGE_33_EXIT_CRITERIA.md`, ADR-072 (`test_stage33_exit_h33x.py`). Stage 34 D1 commercial customer assurance fidelity: `docs/STAGE_34_FIDELITY.md` (`test_stage34_fidelity_d1.py`) maps A1–C1 packs (`docs/ASSURANCE_EVIDENCE_MVP.md`, `docs/COMPLIANCE_QUESTIONNAIRE_MVP.md`); S1/B1 deferred; packaging only — no go-live signed claim. Stage 34 H34x exit + freeze: `docs/STAGE_34_EXIT_CRITERIA.md`, ADR-074 (`test_stage34_exit_h34x.py`). Stage 35 D1 commercial E2E operational smoke fidelity: `docs/STAGE_35_FIDELITY.md` (`test_stage35_fidelity_d1.py`) maps T1–R1 packs (`docs/E2E_ORG_BOOTSTRAP_MVP.md`, `docs/E2E_USERS_RBAC_MVP.md`, `docs/E2E_PURCHASE_STOCK_MVP.md`, `docs/E2E_SALE_PAYMENT_MVP.md`, `docs/E2E_VERIFY_FINANCIALS_MVP.md`, `docs/E2E_BACKUP_RESTORE_MVP.md`); packaging only — no live E2E smoke / go-live signed claim. Stage 35 H35x exit + freeze: `docs/STAGE_35_EXIT_CRITERIA.md`, ADR-076 (`test_stage35_exit_h35x.py`). Stage 36 open (ADR-077): `docs/STAGE_36_PLAN.md` (`test_stage36_open.py`). Stage 36 D1 commercial assurance completion fidelity: `docs/STAGE_36_FIDELITY.md` (`test_stage36_fidelity_d1.py`) maps S1–B1 packs (`docs/SUPPORT_SLA_BOUNDARY_MVP.md`, `docs/BILLING_DEFERRED_HONESTY_MVP.md`); packaging only — no live SLA / paid billing claim. Stage 36 H36x exit + freeze: `docs/STAGE_36_EXIT_CRITERIA.md`, ADR-078 (`test_stage36_exit_h36x.py`). Stage 37 open (ADR-079): `docs/STAGE_37_PLAN.md` (`test_stage37_open.py`). Stage 37 P1: `docs/DATA_PORTABILITY_MVP.md` (`test_data_portability_p1.py`). Stage 37 E1: `docs/ERASURE_HONESTY_MVP.md` (`test_erasure_honesty_e1.py`). Stage 37 D1: `docs/STAGE_37_FIDELITY.md` (`test_stage37_fidelity_d1.py`). Stage 37 H37x exit + freeze: `docs/STAGE_37_EXIT_CRITERIA.md`, ADR-080 (`test_stage37_exit_h37x.py`). Stage 38 open (ADR-081): `docs/STAGE_38_PLAN.md` (`test_stage38_open.py`). Stage 38 V1: `docs/VULN_DISCLOSURE_MVP.md` (`test_vuln_disclosure_v1.py`). Stage 38 B1: `docs/BREACH_NOTIFICATION_MVP.md` (`test_breach_notification_b1.py`). Stage 38 D1: `docs/STAGE_38_FIDELITY.md` (`test_stage38_fidelity_d1.py`). Stage 38 H38x exit + freeze: `docs/STAGE_38_EXIT_CRITERIA.md`, ADR-082 (`test_stage38_exit_h38x.py`). Stage 39 open (ADR-083): `docs/STAGE_39_PLAN.md` (`test_stage39_open.py`). Stage 39 P1: `docs/DPA_SUBPROCESSOR_MVP.md` (`test_dpa_subprocessor_p1.py`). Stage 39 A1: `docs/MSA_ADDENDUM_MVP.md` (`test_msa_addendum_a1.py`). Stage 39 D1: `docs/STAGE_39_FIDELITY.md` (`test_stage39_fidelity_d1.py`). Stage 39 H39x exit + freeze: `docs/STAGE_39_EXIT_CRITERIA.md Stage 40 open: `docs/STAGE_40_PLAN.md`, ADR-085 (`test_stage40_open.py`). Stage 40 U1: `docs/STATUS_UPTIME_MVP.md` (`test_status_uptime_u1.py`). Stage 40 S1 SBOM/dependency disclosure honesty Complete (MVP) Stage 40 D1 availability & supply-chain fidelity Complete (MVP) Stage 40 exit met — `docs/STAGE_40_EXIT_CRITERIA.md`, ADR-086 (`test_stage40_exit_h40x.py`) Stage 41 open: `docs/STAGE_41_PLAN.md`, ADR-087 (`test_stage41_open.py`). Stage 41 A1 accessibility statement honesty Complete (MVP) Stage 41 C1 change/maintenance governance honesty Complete (MVP) Stage 41 D1 accessibility & change governance fidelity Complete (MVP) Stage 41 exit met — `docs/STAGE_41_EXIT_CRITERIA.md`, ADR-088 (`test_stage41_exit_h41x.py`) Stage 42 open: `docs/STAGE_42_PLAN.md`, ADR-089 (`test_stage42_open.py`). Stage 42 A1 AI use disclosure honesty Complete (MVP) Stage 42 P1 AI model/provider boundary honesty Complete (MVP) Stage 42 D1 AI transparency fidelity Complete (MVP) Stage 42 exit met — `docs/STAGE_42_EXIT_CRITERIA.md`, ADR-090 (`test_stage42_exit_h42x.py`) Stage 43 open: `docs/STAGE_43_PLAN.md`, ADR-091 (`test_stage43_open.py`). Stage 43 T1 ToS / AUP honesty Complete (MVP) — `docs/TOS_AUP_MVP.md`, `ops/mvp/tos-aup.json` (`test_tos_aup_t1.py`). Stage 43 C1 Cookie / privacy notice honesty Complete (MVP) — `docs/COOKIE_PRIVACY_NOTICE_MVP.md`, `ops/mvp/cookie-privacy-notice.json` (`test_cookie_privacy_notice_c1.py`). Stage 43 D1 commercial legal notice fidelity Complete (MVP) — `docs/STAGE_43_FIDELITY.md` (`test_stage43_fidelity_d1.py`). Stage 43 exit met — `docs/STAGE_43_EXIT_CRITERIA.md`, ADR-092 (`test_stage43_exit_h43x.py`). Stage 44 open: `docs/STAGE_44_PLAN.md`, ADR-093 (`test_stage44_open.py`). Stage 44 R1 data residency / localization honesty Complete (MVP) — `docs/DATA_RESIDENCY_MVP.md`, `ops/mvp/data-residency.json` (`test_data_residency_r1.py`). Stage 44 E1 encryption / key-management honesty Complete (MVP) — `docs/ENCRYPTION_KMS_MVP.md`, `ops/mvp/encryption-kms.json` (`test_encryption_kms_e1.py`). Stage 44 D1 commercial data trust fidelity Complete (MVP) — `docs/STAGE_44_FIDELITY.md` (`test_stage44_fidelity_d1.py`). Stage 44 exit met — `docs/STAGE_44_EXIT_CRITERIA.md`, ADR-094 (`test_stage44_exit_h44x.py`). Stage 45 open: `docs/STAGE_45_PLAN.md`, ADR-095 (`test_stage45_open.py`). Stage 45 O1 RTO / RPO recovery objectives honesty Complete (MVP) — `docs/RTO_RPO_MVP.md`, `ops/mvp/rto-rpo.json` (`test_rto_rpo_o1.py`). Stage 45 T1 data retention / return honesty Complete (MVP) — `docs/DATA_RETENTION_RETURN_MVP.md`, `ops/mvp/data-retention-return.json` (`test_data_retention_return_t1.py`). Stage 45 D1 commercial continuity & exit fidelity Complete (MVP) — `docs/STAGE_45_FIDELITY.md` (`test_stage45_fidelity_d1.py`). Stage 45 exit met — `docs/STAGE_45_EXIT_CRITERIA.md`, ADR-096 (`test_stage45_exit_h45x.py`). Stage 46 open: `docs/STAGE_46_PLAN.md`, ADR-097 (`test_stage46_open.py`). Stage 46 L1 limitation of liability / indemnity honesty Complete (MVP) — `docs/LIABILITY_INDEMNITY_MVP.md`, `ops/mvp/liability-indemnity.json` (`test_liability_indemnity_l1.py`). Stage 46 W1 service credit / warranty honesty Complete (MVP) — `docs/SERVICE_CREDIT_WARRANTY_MVP.md`, `ops/mvp/service-credit-warranty.json` (`test_service_credit_warranty_w1.py`). Stage 46 D1 commercial liability & remedy fidelity Complete (MVP) — `docs/STAGE_46_FIDELITY.md` (`test_stage46_fidelity_d1.py`). Stage 46 exit met — `docs/STAGE_46_EXIT_CRITERIA.md`, ADR-098 (`test_stage46_exit_h46x.py`). Stage 47 open: `docs/STAGE_47_PLAN.md`, ADR-099 (`test_stage47_open.py`). Stage 47 I1 cyber insurance / COI honesty Complete (MVP) — `docs/CYBER_INSURANCE_MVP.md`, `ops/mvp/cyber-insurance.json` (`test_cyber_insurance_i1.py`). Stage 47 A1 customer audit rights honesty Complete (MVP) — `docs/CUSTOMER_AUDIT_RIGHTS_MVP.md`, `ops/mvp/customer-audit-rights.json` (`test_customer_audit_rights_a1.py`).; Stages 1–42 frozen for Stage 42 scope; external LLM / AI certification Remaining. — `docs/STAGE_42_FIDELITY.md` (`test_stage42_fidelity_d1.py`); maps A1–P1; `ai_certification_claimed` / `external_llm_claimed` remain false; external LLM / AI certification Remaining. — `docs/AI_PROVIDER_BOUNDARY_MVP.md`, `ops/mvp/ai-provider-boundary.json` (`test_ai_provider_boundary_p1.py`); external LLM Remaining. — `docs/AI_USE_DISCLOSURE_MVP.md`, `ops/mvp/ai-use-disclosure.json` (`test_ai_use_disclosure_a1.py`); AI certification Remaining.; Stages 1–41 frozen for Stage 41 scope; WCAG AA audit / public change calendar Remaining. — `docs/STAGE_41_FIDELITY.md` (`test_stage41_fidelity_d1.py`); maps A1–C1; `wcag_aa_claimed` / `change_calendar_live` remain false; WCAG AA audit / public change calendar Remaining. — `docs/CHANGE_GOVERNANCE_MVP.md`, `ops/mvp/change-governance.json` (`test_change_governance_c1.py`); public change calendar Remaining. — `docs/ACCESSIBILITY_STATEMENT_MVP.md`, `ops/mvp/accessibility-statement.json` (`test_accessibility_statement_a1.py`); WCAG AA audit Remaining.; Stages 1–40 frozen for Stage 40 scope; live status page / SBOM pipeline Remaining. — `docs/STAGE_40_FIDELITY.md` (`test_stage40_fidelity_d1.py`); maps U1–S1; `status_page_live` / `sbom_pipeline_live` remain false; live status page / SBOM pipeline Remaining. — `docs/SBOM_DISCLOSURE_MVP.md`, `ops/mvp/sbom-disclosure.json` (`test_sbom_disclosure_s1.py`); live SBOM pipeline Remaining.`, ADR-084 (`test_stage39_exit_h39x.py`). Stage 32 H32x exit + freeze: `docs/STAGE_32_EXIT_CRITERIA.md`, ADR-070 (`test_stage32_exit_h32x.py`). Stage 28 H28x exit + freeze: `docs/STAGE_28_EXIT_CRITERIA.md`, ADR-062 (`test_stage28_exit_h28x.py`).



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
