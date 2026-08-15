"""OpenCode Go MiMo-V2.5 图片识别测试程序

调用图片识别 LLM 的 OpenAI 兼容端点，识别图片内容。

前置：
- 需要图片识别 LLM 的 API Key（OpenCode Go：https://opencode.ai/auth 复制）
- 配置从根目录 .env 文件读取：
    IMAGE_RECOGNIZE_API_URL=OpenAI 兼容端点
    IMAGE_RECOGNIZE_API_KEY=API Key
    IMAGE_RECOGNIZE_MODEL_NAME=模型名（如 mimo-v2.5）

用法：
    python test_mimo_ocr.py <图片路径> [可选的识别指令]
    python test_mimo_ocr.py D:/xxx/photo.jpg "图片里写了什么字？"

参考文档：https://opencode.ai/docs/zh-cn/go
"""
import argparse
import base64
import os
import sys

import requests
from dotenv import load_dotenv

DEFAULT_PROMPT = "请识别这张图片的内容，并尽可能详细地用中文描述图片中看到的一切。"

MAX_LONG_EDGE = 1024  # 压缩后长边像素（宽高比不变）


def load_config() -> dict:
    load_dotenv()  # 读取根目录 .env
    cfg = {
        "url": os.getenv("IMAGE_RECOGNIZE_API_URL", "").strip(),
        "api_key": os.getenv("IMAGE_RECOGNIZE_API_KEY", "").strip(),
        "model": os.getenv("IMAGE_RECOGNIZE_MODEL_NAME", "").strip(),
    }
    missing = [k for k, v in cfg.items() if not v]
    if missing:
        print(f"错误：缺少配置 {', '.join('IMAGE_RECOGNIZE_' + m.upper() for m in missing)}，请在根目录 .env 中配置")
        sys.exit(1)
    return cfg


def image_to_data_uri(path: str) -> str:
    if not os.path.exists(path):
        print(f"错误：图片不存在: {path}")
        sys.exit(1)

    from PIL import Image

    # 压缩：长边缩到 MAX_LONG_EDGE，保持宽高比；小图不放大
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:
        print(f"错误：无法读取图片 {path}: {e}")
        sys.exit(1)

    width, height = img.size
    long_edge = max(width, height)
    if long_edge > MAX_LONG_EDGE:
        scale = MAX_LONG_EDGE / long_edge
        new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
        img = img.resize(new_size, Image.LANCZOS)
        print(f"压缩: {width}x{height} -> {new_size[0]}x{new_size[1]}")

    # 统一转 RGB（PNG 透明通道等）后转 JPEG 压缩体积
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = __import__("io").BytesIO()
    img.save(buf, format="JPEG", quality=85)
    data = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{data}"


def recognize_image(cfg: dict, image_path: str, prompt: str) -> str:
    data_uri = image_to_data_uri(image_path)
    payload = {
        "model": cfg["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        "max_tokens": 2000,
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    print(f"请求端点: {cfg['url']}")
    print(f"使用模型: {cfg['model']}")
    print(f"识别图片: {image_path}")

    resp = requests.post(cfg["url"], json=payload, headers=headers, timeout=120)
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        print(f"响应解析失败: {e}")
        print(data)
        sys.exit(1)

    usage = data.get("usage", {})
    print(f"Token 用量: {usage}")
    return content


def main():
    parser = argparse.ArgumentParser(description="使用 OpenCode Go MiMo-V2.5 识别图片内容")
    parser.add_argument("image", help="图片文件路径")
    parser.add_argument("prompt", nargs="?", default=DEFAULT_PROMPT, help="识别指令（可选）")
    args = parser.parse_args()

    cfg = load_config()
    result = recognize_image(cfg, args.image, args.prompt)

    print("\n==== 识别结果 ====")
    print(result)


if __name__ == "__main__":
    main()
