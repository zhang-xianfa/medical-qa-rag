FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
# 国内服务器走 npm 镜像，否则 registry.npmjs.org 经常超时
RUN npm config set registry https://registry.npmmirror.com && npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
