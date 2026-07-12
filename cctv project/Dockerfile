# ============================================
# VisionGuard Frontend — Production Dockerfile
# ============================================

# Stage 1: Build the Vite production assets
FROM node:20-alpine AS builder

WORKDIR /app

# Install package dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source files and compile
COPY . .
RUN npm run build

# Stage 2: Serve the compiled static assets with Nginx
FROM nginx:1.27-alpine

# Copy static files to default Nginx share
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration block
COPY nginx/nginx_frontend.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
