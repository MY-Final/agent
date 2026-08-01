# 投标分析 Agent 后端镜像
# 默认不包含 PaddleOCR（CPU 版体积约 2GB+）；需要扫描件 OCR 时使用：
#   docker build -t tender-backend --build-arg WITH_OCR=true ./backend
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG WITH_OCR=false

# 安装依赖：默认剔除 paddleocr/paddlepaddle，显著减小镜像体积
COPY requirements.txt ./
RUN grep -v -E '^(paddleocr|paddlepaddle)' requirements.txt > requirements.docker.txt \
    && pip install -r requirements.docker.txt \
    && rm -f requirements.docker.txt

# 可选 OCR：CPU 版 PaddlePaddle 与运行库
RUN if [ "$WITH_OCR" = "true" ]; then \
        apt-get update \
        && apt-get install -y --no-install-recommends libgomp1 \
        && rm -rf /var/lib/apt/lists/* \
        && pip install paddleocr==3.7.0 paddlepaddle==3.3.1; \
    fi

COPY . .

EXPOSE 8000

# 启动时自动建表/执行幂等迁移；单进程即可，LangGraph 检查点依赖 PostgreSQL
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
