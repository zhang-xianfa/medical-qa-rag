FROM python:3.11-slim

WORKDIR /app

# 系统依赖：不装 curl（容器内 apt 源在国内经常连不上），健康检查改用 Python 标准库

# Python 依赖（直连 PyPI 慢；实测清华镜像 14s，阿里云要 2m36s）
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 60 -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt gunicorn

# 向量检索依赖：CPU 版 torch + sentence-transformers
# torch 走上海交大镜像（download.pytorch.org 在国内只有 ~150KB/s）
# 注意版本下限：transformers 5.x 要求 torch >= 2.6，低于这个值会静默禁用 PyTorch，
# 表现为 embedding 全部生成失败（RAG 静默失效），所以锁 2.9.1（与本地环境一致）
RUN pip install --no-cache-dir --timeout 60 \
    --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cpu \
    torch==2.9.1+cpu

# 锁版本：与本地验证过、能加载 bge-small-zh-v1.5 的组合一致。
# 更新版 ST 对缺失 1_Pooling/config.json 的模型更严格，会直接报错。
RUN pip install --no-cache-dir --timeout 60 -i https://pypi.tuna.tsinghua.edu.cn/simple \
    sentence-transformers==5.3.0 \
    transformers==5.5.0

# 应用代码
COPY . .

# 本地 embedding 模型（bge-small-zh-v1.5, 512 维），镜像内离线加载
ENV ST_MODEL_PATH=/app/models/bge-small-zh-v1.5 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

# 非 root 运行
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

EXPOSE 8000

# gunicorn + 2 uvicorn workers（2核2G 机器：每个 worker 都要加载一份 torch 模型）
CMD ["gunicorn", "api.main:app", \
     "--workers", "2", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "180", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
