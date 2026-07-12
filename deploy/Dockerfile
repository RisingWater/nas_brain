FROM ubuntu:24.04

ENV UID=1002
ENV DEBIAN_FRONTEND=noninteractive

# 替换为阿里云镜像加速
RUN sed -i 's/archive.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirrors.aliyun.com/g' /etc/apt/sources.list

# 系统依赖
RUN apt-get update && apt-get install -y \
    sudo \
    git \
    vim \
    curl \
    python3 \
    python3-pip \
    python3-venv \
    alsa-utils \
    pulseaudio \
    pulseaudio-utils \
    ffmpeg \
    sox \
    libasound2-dev \
    portaudio19-dev \
    cups \
    cups-client \
    libreoffice \
    libreoffice-writer \
    locales \
    locales-all \
    && rm -rf /var/lib/apt/lists/*

# 创建用户并加入组
RUN useradd -m -u $UID appuser && \
    usermod -a -G audio,pulse,pulse-access,sudo,lp,lpadmin appuser

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
    apt-get update && apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/* && \
    npm install -g @anthropic-ai/claude-code && \
    npm install -g bun

USER appuser
CMD ["bash", "deploy/run.sh"]
