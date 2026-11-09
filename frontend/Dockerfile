# Production image for the website + portal. Build (from the repo root):
#   docker build -t kjs-web --build-arg SITE_URL=https://www.kjsindia.com ./frontend
# Three stages: install packages → build → copy only the built server into a small image.

FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Baked in at build time: the /api rewrite target and the address used in sitemap/robots.
ARG API_INTERNAL_URL=http://backend:8000
ARG SITE_URL=http://localhost:3000
# Public address of the R2 bucket with the site pictures (src/lib/assets.ts). Empty = public/ folder.
ARG NEXT_PUBLIC_ASSET_BASE=
ENV API_INTERNAL_URL=$API_INTERNAL_URL \
    SITE_URL=$SITE_URL \
    NEXT_PUBLIC_ASSET_BASE=$NEXT_PUBLIC_ASSET_BASE \
    NEXT_STANDALONE=1 \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0
ARG API_INTERNAL_URL=http://backend:8000
ARG SITE_URL=http://localhost:3000
ARG NEXT_PUBLIC_ASSET_BASE=
ENV API_INTERNAL_URL=$API_INTERNAL_URL \
    SITE_URL=$SITE_URL \
    NEXT_PUBLIC_ASSET_BASE=$NEXT_PUBLIC_ASSET_BASE
# The "node" user comes with the image: never run as root.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD wget -qO /dev/null http://127.0.0.1:3000/healthz || exit 1
CMD ["node", "server.js"]
