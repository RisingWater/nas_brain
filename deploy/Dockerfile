FROM ubuntu:24.04

ENV UID=1002
ENV DEBIAN_FRONTEND=noninteractive

# 替换 apt 源为阿里云镜像（Ubuntu 24.04 使用 .sources 格式）
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/ubuntu.sources && \
    sed -i 's|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list.d/ubuntu.sources

# 系统基础依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    sudo git curl vim \
    python3 python3-pip python3-venv \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 音频依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils pulseaudio pulseaudio-utils \
    ffmpeg sox libasound2-dev portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# CUPS 打印
RUN apt-get update && apt-get install -y --no-install-recommends \
    cups cups-client printer-driver-hpcups libcups2-dev \
    && rm -rf /var/lib/apt/lists/*

# LibreOffice（大包，不需要时可注释）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# Locale
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales locales-all \
    && rm -rf /var/lib/apt/lists/*

# 创建用户并加入组
RUN useradd -m -u $UID appuser && \
    usermod -a -G audio,pulse,pulse-access,sudo,lp,lpadmin appuser && \
    echo "appuser ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# PulseAudio 配置
RUN mkdir -p /var/run/pulse && \
    chown appuser:appuser /var/run/pulse && \
    chmod 755 /var/run/pulse && \
    echo "load-module module-native-protocol-unix auth-anonymous=1 socket=/var/run/pulse/native" > /etc/pulse/default.pa && \
    echo "load-module module-always-sink" >> /etc/pulse/default.pa && \
    echo "load-module module-suspend-on-idle" >> /etc/pulse/default.pa

# CUPS 配置
RUN echo "ServerName /run/cups/cups.sock" >> /etc/cups/client.conf

# 中文 locale
RUN locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8
ENV LANG=zh_CN.UTF-8
ENV LANGUAGE=zh_CN:zh
ENV LC_ALL=zh_CN.UTF-8

RUN git config --global --add safe.directory "*"
RUN git config --global --add safe.directory /workdir

WORKDIR /workdir

# Node.js + Claude Code CLI + Bun
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/* && \
    npm install -g @anthropic-ai/claude-code && \
    npm install -g bun

USER appuser
CMD ["bash", "deploy/run.sh"]
