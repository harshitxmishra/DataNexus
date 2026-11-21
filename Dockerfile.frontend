# ============================================================
# DataNexus v2.0.0 Frontend — Multi-Stage Production Dockerfile
# Vite/React 18 build -> Nginx Alpine static serving + SSE Proxy
# ============================================================

# Stage 1: Build React 18 / Vite TypeScript SPA
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci --prefer-offline --no-audit

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Nginx Server
FROM nginx:1.27-alpine AS runtime

# Remove default nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
