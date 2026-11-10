# ---- 前端构建 ----
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 运行环境 ----
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=Asia/Seoul DATA_DIR=/data
WORKDIR /app
COPY pyproject.toml README.md ./
COPY screener/ screener/
COPY server/ server/
RUN pip install ".[server]"
COPY --from=web /web/dist web/dist
RUN useradd --create-home --uid 1000 app && mkdir -p /data && chown app /data
COPY docker-entrypoint.sh /usr/local/bin/
# Windows 检出可能带 CRLF 换行或丢失执行权限，这里统一修正
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/api/health')"
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
