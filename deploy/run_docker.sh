#!/bin/bash
set -e

cd "$(dirname "$0")/.."

IMAGE="nas-brain"
NAME="nas-brain"
WORKDIR="/vol1/ai/nas_brain"

# 构建镜像
echo "=== Building Docker image ==="
docker build -t $IMAGE -f deploy/Dockerfile .

# 清理旧容器
docker stop $NAME 2>/dev/null || true
docker rm $NAME 2>/dev/null || true

# 启动
echo "=== Starting $NAME ==="
docker run -d -it --name $NAME \
    --privileged \
    --device /dev/snd:/dev/snd \
    -v $WORKDIR:/workdir \
    -e PULSE_RUNTIME_PATH=/workdir/pulse \
    -p 9020:9020 \
    --restart unless-stopped \
    $IMAGE

echo ""
echo "=== Done ==="
echo "  Web:  http://localhost:9020"
echo "  Logs: docker logs -f $NAME"
echo "  Shell: docker exec -it $NAME bash"
echo "  Stop:  docker stop $NAME"
