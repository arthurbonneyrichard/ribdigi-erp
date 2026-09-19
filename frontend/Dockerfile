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
ARG NEXT_PUBLIC_UMAMI_SRC=https://analytics.ribdigihouse.com/script.js
ARG NEXT_PUBLIC_UMAMI_WEBSITE_ID=0d5b3d4e-fe16-47bf-91f2-6ce564fb2e0e
ARG NEXT_PUBLIC_UMAMI_DOMAINS=erp.ribdigihouse.com
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_PUBLIC_UMAMI_SRC=${NEXT_PUBLIC_UMAMI_SRC} \
    NEXT_PUBLIC_UMAMI_WEBSITE_ID=${NEXT_PUBLIC_UMAMI_WEBSITE_ID} \
    NEXT_PUBLIC_UMAMI_DOMAINS=${NEXT_PUBLIC_UMAMI_DOMAINS}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system --gid 10001 nodejs \
    && adduser --system --uid 10001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/guides ./guides
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://127.0.0.1:3000/',(r)=>{process.exit(r.statusCode&&r.statusCode<500?0:1)}).on('error',()=>process.exit(1))"

CMD ["node", "server.js"]
