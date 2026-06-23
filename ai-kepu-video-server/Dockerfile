FROM python:3.12-slim

USER root
ENV LANG zh_CN.UTF-8
ENV TZ=Asia/Shanghai
ENV PIP_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple

# 设置时区
RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 使用阿里云镜像源并安装系统依赖
RUN set -eux; \
    release=$(. /etc/os-release && echo $VERSION_CODENAME); \
    rm -f /etc/apt/sources.list.d/*; \
    printf 'deb https://mirrors.aliyun.com/debian/ %s main non-free non-free-firmware contrib\n' "$release" > /etc/apt/sources.list; \
    printf 'deb https://mirrors.aliyun.com/debian-security/ %s-security main non-free non-free-firmware contrib\n' "$release" >> /etc/apt/sources.list; \
    printf 'deb https://mirrors.aliyun.com/debian/ %s-updates main non-free non-free-firmware contrib\n' "$release" >> /etc/apt/sources.list; \
    apt-get clean; \
    apt-get update -o Acquire::http::Timeout=10 -o Acquire::https::Timeout=10; \
    apt-get install -y --no-install-recommends ffmpeg fonts-noto-cjk wget gnupg; \
    rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . /app

# 创建输出目录
RUN mkdir -p /app/output/drafts /app/logs

# 设置 PYTHONPATH
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 2002

# 启动命令
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "2002", "--proxy-headers", "--forwarded-allow-ips", "*"]
