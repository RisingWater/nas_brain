#!/bin/bash
set -e

cd "$(dirname "$0")/.."

IMAGE="nas-brain"
NAME="nas-brain"
WORKDIR="/vol1/ai/nas_brain"

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
    -p 631:631 \
    --restart unless-stopped \
    $IMAGE

echo ""
echo "=== Done ==="
echo "  Web:  http://localhost:9020"
echo "  CUPS: http://localhost:631"
echo "  Logs: docker logs -f $NAME"
echo "  Shell: docker exec -it $NAME bash"
echo "  Stop:  docker stop $NAME"
echo ""
echo "Add printer:"
echo "  docker exec -it $NAME sudo lpadmin -p HP2600 -E -v ipp://192.168.1.186 -m everywhere"
echo "  docker exec -it $NAME sudo lpoptions -d HP2600"
