#!/bin/bash
set -e

cd /workdir

# 更新代码（如果可访问 git）
if [ -d .git ] && git status &> /dev/null; then
    echo "Updating code..."
    git pull || true
fi

# ---- 构建前端 ----
cd /workdir/frontend
bun install
bun run build
cd /workdir

# ---- PulseAudio ----
echo "Shutting down PulseAudio if exist..."
pulseaudio --kill 2>/dev/null || true
sleep 2

echo "Starting PulseAudio..."
pulseaudio --start --exit-idle-time=-1 --log-target=stderr &
sleep 2

MAX_RETRIES=30
RETRY_COUNT=0
PULSE_STARTED=false

echo "Waiting for PulseAudio to start..."
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if pactl info &> /dev/null; then
        PULSE_STARTED=true
        echo "PulseAudio started successfully"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ "$PULSE_STARTED" = false ]; then
    echo "PulseAudio failed, retrying forcefully..."
    killall pulseaudio 2>/dev/null || true
    sleep 3
    pulseaudio --start --exit-idle-time=-1 --log-target=stderr &
    sleep 5
    if pactl info &> /dev/null; then
        PULSE_STARTED=true
    else
        echo "WARNING: PulseAudio startup failed, audio may not work"
    fi
fi

if [ "$PULSE_STARTED" = true ]; then
    echo "Enabling anonymous connections..."
    pactl load-module module-native-protocol-unix auth-anonymous=1 2>/dev/null || true

    echo "Cleaning up existing audio modules..."
    pactl unload-module module-null-sink 2>/dev/null || true
    pactl unload-module module-alsa-sink 2>/dev/null || true
    pactl unload-module module-alsa-source 2>/dev/null || true
    sleep 1

    echo "Loading ALSA sink (speaker)..."
    SINK_MODULE=$(pactl load-module module-alsa-sink device=hw:0,0 sink_name=alsa_output 2>/dev/null || true)
    if [ -n "$SINK_MODULE" ]; then
        echo "ALSA sink loaded, module: $SINK_MODULE"
        pactl set-default-sink alsa_output
        pactl set-sink-volume alsa_output 150% 2>/dev/null || true
    else
        echo "WARNING: ALSA sink load failed, speaker may not work"
    fi

    echo "Audio devices:"
    pactl list sinks short 2>/dev/null || true
    pactl list sources short 2>/dev/null || true
    echo "Audio initialization complete"
fi

# ---- 虚拟环境 ----
cd /workdir
if [ ! -d venv ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
else
    echo "Virtual environment exists, checking dependencies..."
    venv/bin/pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --quiet || true
fi

# ---- Claude Code 配置 ----
mkdir -p ~/.claude
if [ -f /workdir/.claude/settings.json ]; then
    cp /workdir/.claude/settings.json ~/.claude/settings.json
    echo "Claude Code settings loaded"
fi

# 限制 glibc 内存池
export MALLOC_ARENA_MAX=4

# ---- 启动 service_manager（自动拉起所有微服务） ----
echo "Starting NAS Brain service manager..."
exec venv/bin/python deploy/start_scripts/service_manager.py
