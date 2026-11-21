# Next.js — development stage (local compose) + production standalone runner.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Local development (hot reload). Used by docker-compose.yml via target: development
FROM node:20-alpine AS development
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 \
    NODE_ENV=production
ARG NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
# Analytics is off unless both of these are passed at build time.
ARG NEXT_PUBLIC_UMAMI_SRC=
ARG NEXT_PUBLIC_UMAMI_WEBSITE_ID=
ARG NEXT_PUBLIC_UMAMI_DOMAINS=erp.ribdigihouse.com
# Optional tile provider for the staff map (OpenStreetMap when empty).
ARG NEXT_PUBLIC_MAP_TILE_URL=
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_UMAMI_SRC=${NEXT_PUBLIC_UMAMI_SRC} \
    NEXT_PUBLIC_UMAMI_WEBSITE_ID=${NEXT_PUBLIC_UMAMI_WEBSITE_ID} \
    NEXT_PUBLIC_UMAMI_DOMAINS=${NEXT_PUBLIC_UMAMI_DOMAINS} \
    NEXT_PUBLIC_MAP_TILE_URL=${NEXT_PUBLIC_MAP_TILE_URL}
COPY --from=deps /app/node_modules ./node_modules
# Stamp is in the frontend context so a rebuild cannot reuse an image whose
# context still hashes as the old production tree.
COPY ribdigi-build-id.txt /tmp/ribdigi-build-id.txt
RUN tr -d '\r' < /tmp/ribdigi-build-id.txt | awk 'NF { print; exit }' > /tmp/ribdigi-build-id.one \
    && grep -Eq '^[0-9a-f]{12}$' /tmp/ribdigi-build-id.one \
    && ! grep -Fxq '20261003-live-test-store-scope' /tmp/ribdigi-build-id.one \
    && ! grep -Fxq '20261008-alembic-single-head-0136' /tmp/ribdigi-build-id.one
COPY . .
# Never reuse a host/layer .next; standalone runner copies this same build.
RUN rm -rf .next && npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
# Starts server.js with framework-identifying headers removed (security control 09).
COPY --from=builder --chown=nextjs:nodejs /app/serve.cjs ./serve.cjs

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3000/',(r)=>{process.exit(r.statusCode&&r.statusCode<500?0:1)}).on('error',()=>process.exit(1))"

CMD ["node", "serve.cjs"]
