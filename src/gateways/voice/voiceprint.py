"""语音网关 — 声纹识别（ModelScope ERes2NetV2）"""
import os
import shutil
import logging
import numpy as np
import requests
from src.common.utils import cfg

logger = logging.getLogger("voice_gateway.voiceprint")

_RECORD_DIR = os.getenv("RECORD_DIR", "data/recordings")
_TEMP_USER_ID = "u_temp_voice"


class VoiceprintEngine:
    """声纹识别引擎"""

    def __init__(self):
        self._pipeline = None

    def load(self):
        """加载模型"""
        if self._pipeline is not None:
            return
        try:
            from modelscope.pipelines import pipeline as mspipeline
            from modelscope.utils.constant import Tasks
            self._pipeline = mspipeline(
                Tasks.speaker_verification,
                model='iic/speech_eres2netv2_sv_zh-cn_16k-common',
            )
            logger.info("声纹模型已加载 (ERes2NetV2)")
        except ImportError:
            logger.error("modelscope 未安装，声纹功能不可用")
            raise

    def extract(self, wav_path: str) -> np.ndarray:
        """提取说话人嵌入向量（192维）"""
        if not self._pipeline:
            raise RuntimeError("声纹模型未加载")
        try:
            result = self._pipeline([wav_path, wav_path], output_emb=True)
            emb = result["embs"][0]
            return np.array(emb, dtype=np.float32)
        except Exception as e:
            logger.error("声纹提取失败: %s", e, exc_info=True)
            raise

    def detect(self, wav_path: str, wakeword_id: str = "") -> tuple[str, str]:
        """声纹检测：提取 → POST db_services 匹配 → 返回 (user_id, speaker_name)"""
        try:
            emb = self.extract(wav_path)
            vector_list = emb.tolist()

            # 调 db_services 声纹检测
            url = cfg.get_service_url("db_services", "/api/voiceprints/detect")
            resp = requests.post(url, json={"vector": vector_list}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                best_uid = data.get("best_user_id")

                if best_uid:
                    user_id = best_uid
                    speaker = data.get("best_name", best_uid)
                    logger.info("声纹匹配: %s (%.2f%%)", speaker, data.get("best_avg", 0) * 100)
                else:
                    user_id = _TEMP_USER_ID
                    speaker = "未知用户"
                    logger.info("声纹无匹配，使用临时用户: %s", _TEMP_USER_ID)

                # 注册声纹（临时用户也注册，后续可手动分配）
                self._enroll_to_db(user_id, vector_list, wav_path)

                # 移动音频到用户目录
                self._move_audio(wav_path, user_id)
                return user_id, speaker

        except Exception as e:
            logger.error("声纹检测失败: %s", e)

        return _TEMP_USER_ID, "未知用户"

    def _enroll_to_db(self, user_id: str, vector: list, audio_path: str):
        """注册声纹到 db_services"""
        try:
            url = cfg.get_service_url("db_services", "/api/voiceprints/enroll")
            requests.post(url, json={
                "user_id": user_id,
                "vector": vector,
                "audio_path": audio_path,
                "vp_type": "auto",
            }, timeout=10)
        except Exception as e:
            logger.error("声纹注册失败: %s", e)

    def _move_audio(self, wav_path: str, user_id: str):
        """移动录音到用户目录"""
        try:
            target_dir = os.path.join(_RECORD_DIR, user_id)
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, os.path.basename(wav_path))
            shutil.move(wav_path, target)
        except Exception as e:
            logger.warning("移动音频失败: %s", e)
