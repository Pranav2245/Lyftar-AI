# Build stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json .
RUN npm install
COPY vite.config.js .
COPY index.html .
COPY src ./src
RUN npm run build

# Production stage – nginx
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
