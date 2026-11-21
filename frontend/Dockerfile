# syntax=docker/dockerfile:1.7
# PointQR web image (ADR-0014): Angular production build served by nginx, which also proxies
# /api and /ws to the API container.
FROM node:24.22.3-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund
COPY . .
RUN npx ng build --configuration production \
 && node nginx/csp-hashes.mjs dist/pointqr/browser/index.html > /tmp/script-hashes

FROM nginx:1.29-alpine AS web
COPY --from=build /app/dist/pointqr/browser /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /tmp/script-hashes /tmp/script-hashes
RUN sed -i "s|__SCRIPT_HASHES__|$(cat /tmp/script-hashes)|" /etc/nginx/snippets/security-headers.conf \
 && rm /tmp/script-hashes \
 && grep -q "sha256-" /etc/nginx/snippets/security-headers.conf
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --retries=10 \
  CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
