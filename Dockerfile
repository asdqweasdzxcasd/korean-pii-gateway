FROM python:3.12-slim
WORKDIR /app
COPY packages/core /app/packages/core
COPY packages/gateway /app/packages/gateway
RUN pip install --no-cache-dir /app/packages/core /app/packages/gateway
EXPOSE 8500
# 감사 로그는 기본 stdout — docker logs로 수집
CMD ["uvicorn", "--factory", "korean_pii_gateway.app:create_app", "--host", "0.0.0.0", "--port", "8500"]
