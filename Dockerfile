# AI 英语刷题机 - 后端生产镜像（Zeabur / 任意云平台通用）
# 构建: docker build -t epm .
# 运行: docker run -d -p 8765:8765 -e EPM_API_KEY=xxx epm
FROM python:3.11-slim

WORKDIR /app

# 依赖层（利用缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY backend/ backend/
COPY run_app.py .

# 前端构建产物（可选：包含时后端直接托管网页）
# COPY frontend/dist/ frontend/dist/

# 环境变量（生产必须）
ENV EPM_API_KEY="" \
    EPM_RATE_LIMIT="120" \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=3)" || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8765"]
