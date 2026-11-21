FROM public.ecr.aws/docker/library/node:24.11.1-bookworm-slim AS build
WORKDIR /opt/cfo
COPY package*.json .npmrc ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY . .
RUN npm run build

FROM public.ecr.aws/docker/library/node:24.11.1-bookworm-slim
WORKDIR /opt/cfo
COPY --from=build /opt/cfo/build ./build
COPY package.json ./
ENV NODE_ENV=production HOST=0.0.0.0 PORT=8080
USER 1001
EXPOSE 8080
CMD ["node", "build"]
