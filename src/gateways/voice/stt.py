"""语音网关 — STT 语音转文字（FunASR SenseVoiceSmall）"""
import os
import re
import logging

logger = logging.getLogger("voice_gateway.stt")

_TAG_PATTERN = re.compile(r"<\|[^|]+\|>")


class STT:
    """语音转文字引擎"""

    def __init__(self):
        self._model = None

    def load(self):
        """加载模型（延迟加载）"""
        if self._model is not None:
            return
        try:
            from funasr import AutoModel
            disable_update = os.getenv("DISABLE_UPDATE", "1") == "1"
            self._model = AutoModel(
                model="iic/SenseVoiceSmall",
                disable_update=disable_update,
                device="cpu",
                ncpu=1,
            )
            logger.info("STT 模型已加载 (SenseVoiceSmall)")
        except ImportError:
            logger.error("funasr 未安装，STT 不可用")
            raise

    def transcribe(self, wav_path: str) -> str:
        """语音转文字，返回文本"""
        if not self._model:
            raise RuntimeError("STT 模型未加载")
        if not os.path.exists(wav_path):
            logger.error("音频文件不存在: %s", wav_path)
            return ""

        try:
            result = self._model.generate(
                input=wav_path,
                language="auto",
                use_itn=True,
                batch_size_s=30,
            )
            raw = result[0]["text"] if result else ""
            if "<|nospeech|>" in raw:
                return ""
            # 清理 SenseVoice 标签
            text = _TAG_PATTERN.sub("", raw).strip()
            return text
        except Exception as e:
            logger.error("STT 识别失败: %s", e, exc_info=True)
            return ""
