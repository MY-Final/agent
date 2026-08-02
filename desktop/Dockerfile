# 前端 Web 构建：Vite 产物由 nginx 托管，/api 与 /health 反代到 backend 服务。
# 构建参数 VITE_BACKEND_URL 可选：留空时前端同源访问（推荐，由 nginx 反代）。
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_BACKEND_URL
ENV VITE_BACKEND_URL=$VITE_BACKEND_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
