FROM node:22-alpine AS base

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# No build-time API_URL needed — the /api/* proxy is a Route Handler that
# reads process.env.API_URL at request time. One image, configurable per env.
RUN npm run build


FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3001
ENV HOSTNAME=0.0.0.0

# node:alpine ships a non-root `node` user (uid 1000). chown the standalone
# output so it can run as that user.
COPY --from=base --chown=node:node /app/.next/standalone ./
COPY --from=base --chown=node:node /app/.next/static ./.next/static
COPY --from=base --chown=node:node /app/public ./public

USER node

EXPOSE 3001

# wget is in BusyBox (default on alpine). --spider does a HEAD-style check.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider "http://localhost:${PORT:-3001}/healthz" || exit 1

CMD ["node", "server.js"]
