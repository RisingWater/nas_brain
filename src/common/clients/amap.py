"""高德地图 API 客户端 — 静态图等"""
import os
import logging
import requests

logger = logging.getLogger(__name__)


class AmapAPI:
    """高德地图 API"""

    def __init__(self):
        self._api_key = os.getenv("AMAP_API_KEY", "")
        if not self._api_key:
            logger.warning("AMAP_API_KEY 未设置，地图功能不可用")

    def get_static_map(self, longitude: float, latitude: float, zoom: int = 17,
                       size: str = "800*800", marker_style: str = "mid,,A",
                       save_path: str | None = None) -> str | None:
        """获取高德静态地图图片

        Args:
            longitude: 经度
            latitude: 纬度
            zoom: 缩放级别 1-18
            size: 图片尺寸 '宽*高'
            marker_style: 标记样式
            save_path: 保存路径，None 则自动生成

        Returns:
            保存的文件路径，失败返回 None
        """
        if not self._api_key:
            return None

        if not save_path:
            save_path = f"data/map_{longitude}_{latitude}.png"
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)

        try:
            resp = requests.get(
                "https://restapi.amap.com/v3/staticmap",
                params={
                    "location": f"{longitude},{latitude}",
                    "zoom": zoom,
                    "size": size,
                    "markers": f"{marker_style}:{longitude},{latitude}",
                    "key": self._api_key,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                logger.info("地图图片已保存: %s", save_path)
                return save_path
            logger.error("地图API失败: %s", resp.status_code)
        except Exception as e:
            logger.error("获取地图图片异常: %s", e)
        return None
