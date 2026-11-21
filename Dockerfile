# Build React frontend
FROM node:22-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# Backend and web server
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    libxcb1 \
    libgl1 \
    nginx \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# Include built frontend
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html

# Add web server configuration and startup script
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY start.sh /start.sh

RUN rm -f /etc/nginx/sites-enabled/default \
    && sed -i 's/\r$//' /start.sh \
    && chmod +x /start.sh

EXPOSE 10000

CMD ["/start.sh"]
