
# 从一个 Python 3.10 的基础环境开始
# 把项目放进 /app
# 安装 requirements.txt
# 启动时运行 python -m app.main

FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=5001
ENV FLASK_DEBUG=false
EXPOSE 5001

CMD ["python", "-m", "app.main"]
