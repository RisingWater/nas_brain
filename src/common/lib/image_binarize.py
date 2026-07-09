"""图片二值化处理工具 — 去阴影 + 对比度增强 + 二值化"""
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ImageBinarrize:
    """图片二值化处理器"""

    def remove_shadows_simple_contrast(self, img_path, kernel_size=501, contrast=1.8, brightness=0):
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"无法读取图像: {img_path}")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_float = gray.astype(np.float32)
        if kernel_size % 2 == 0:
            kernel_size += 1
        background = cv2.GaussianBlur(gray_float, (kernel_size, kernel_size), 0)
        divided = gray_float / (background + 1e-7)
        normalized = cv2.normalize(divided, None, 0, 255, cv2.NORM_MINMAX)
        shadow_removed = normalized.astype(np.uint8)
        result = cv2.convertScaleAbs(shadow_removed, alpha=contrast, beta=brightness)
        return result, shadow_removed, gray

    def binarize_image(self, image, threshold=127, invert=False):
        if invert:
            _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY_INV)
        else:
            _, binary = cv2.threshold(image, threshold, 255, cv2.THRESH_BINARY)
        return binary

    def process_image(self, input_path, output_path):
        final_result, _ = self.process_pipeline(
            input_path, kernel_size=601, contrast=2.0, brightness=10,
            binarize=True, threshold=192, invert=False,
        )
        cv2.imwrite(output_path, final_result)

    def process_pipeline(self, img_path, kernel_size=601, contrast=2.0, brightness=10,
                         binarize=True, threshold=160, invert=False):
        enhanced, shadow_removed, original = self.remove_shadows_simple_contrast(
            img_path, kernel_size, contrast, brightness
        )
        final_result = enhanced
        if binarize:
            final_result = self.binarize_image(enhanced, threshold, invert)
        return final_result, enhanced
