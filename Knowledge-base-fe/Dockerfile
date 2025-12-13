## Multi-stage Dockerfile for Next.js (production)
## Build with: docker build -t knowledge-base-fe .
## Run with:   docker run -p 3000:3000 --env-file .env knowledge-base-fe

# 1) Base image for all stages (Debian-based to avoid musl native module issues)
FROM node:20-slim AS base
WORKDIR /app
# Install minimal required system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# 2) Install dependencies for building (full deps incl. dev)
FROM base AS deps
COPY package.json package-lock.json ./
# Use npm ci for reproducible installs
RUN npm ci

# 3) Build the Next.js app
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Build the app
RUN npm run build

# 4) Prepare production-only node_modules (smaller image)
FROM base AS prod-deps
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# 5) Runtime image
FROM base AS runner
WORKDIR /app

# Non-root user for security (already exists in node image)
USER node

# Copy production node_modules and built assets
COPY --chown=node:node --from=prod-deps /app/node_modules ./node_modules
COPY --chown=node:node --from=builder /app/.next ./.next
COPY --chown=node:node package.json ./package.json
COPY --chown=node:node next.config.mjs ./next.config.mjs

# Set the port Next.js listens on
EXPOSE 3000

# Start Next.js in production mode
CMD ["node_modules/.bin/next", "start", "-p", "3000"]