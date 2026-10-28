# syntax=docker/dockerfile:1

# ---------- Build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies from the lockfile first for better layer caching.
COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json vite.config.ts postcss.config.js tailwind.config.js index.html ./
COPY public ./public
COPY src ./src

# Bake the API base URL into the bundle. In Compose the browser talks to
# nginx on the same host, and nginx proxies /api/* to the api service.
ARG VITE_API_BASE_URL=/api/v1
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# ---------- Runtime stage ----------
FROM nginx:1.27-alpine AS runtime

RUN rm -rf /usr/share/nginx/html/* /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
# Full main config (not a conf.d snippet): it moves the pid and temp paths to
# /tmp so nginx can run as an unprivileged user.
COPY nginx.conf /etc/nginx/nginx.conf

RUN addgroup -g 10002 -S windiq \
    && adduser -u 10002 -S -G windiq windiq \
    && chown -R windiq:windiq /usr/share/nginx/html

# Validate the config as the runtime user: running `nginx -t` as root would
# create a root-owned /tmp/nginx.pid that the unprivileged server cannot replace.
USER windiq

RUN nginx -t

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1

CMD ["nginx", "-g", "daemon off;"]
