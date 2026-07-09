"""公众号链接转 DOCX 工具 — 获取网页内容，嵌入图片，输出 DOCX"""
import os
import re
import base64
import urllib.parse
import logging
import requests
from bs4 import BeautifulSoup
from docx import Document

logger = logging.getLogger(__name__)


class FixedWebConverter:
    """网页链接 → DOCX 转换器"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        self.base_url = None

    def convert_url_to_docx(self, url: str, output_dir: str) -> str | None:
        """下载网页并转换为 DOCX 文件"""
        try:
            html_content, html_title = self._fetch_and_clean(url)
            safe_title = re.sub(r'[<>:"/\\|?*]', '', html_title or "网页").replace(' ', '_')
            output_path = os.path.join(output_dir, f"{safe_title}.docx")
            if self._html_to_docx(html_content, output_path):
                self._remove_empty_paragraphs(output_path)
                return output_path
        except Exception as e:
            logger.error("转换失败: %s", e)
        return None

    def _fetch_and_clean(self, url: str) -> tuple[str, str]:
        resp = self.session.get(url, timeout=30)
        resp.raise_for_status()
        self.base_url = url
        soup = BeautifulSoup(resp.content, 'html.parser')
        page_title = "无标题"
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            page_title = og_title['content'].strip()
        else:
            title_tag = soup.find('title')
            if title_tag and title_tag.get_text():
                page_title = title_tag.get_text().strip()
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src')
            if src:
                data_uri = self._download_image(src)
                if data_uri:
                    img['src'] = data_uri
        main = soup.find('main') or soup.find('article') or soup.find('body')
        return str(main), page_title

    def _download_image(self, img_url: str) -> str | None:
        if not img_url.startswith('http') and self.base_url:
            img_url = urllib.parse.urljoin(self.base_url, img_url)
        elif not img_url.startswith('http'):
            return None
        try:
            resp = self.session.get(img_url, timeout=10)
            resp.raise_for_status()
            b64 = base64.b64encode(resp.content).decode('utf-8')
            ct = resp.headers.get('content-type', 'image/jpeg')
            return f"data:{ct};base64,{b64}"
        except Exception as e:
            logger.warning("下载图片失败 %s: %s", img_url, e)
            return None

    def _html_to_docx(self, html: str, output_path: str) -> bool:
        try:
            import pypandoc
            pypandoc.convert_text(html, to='docx', format='html', outputfile=output_path,
                                  extra_args=['--standalone', '--embed-resources', '--toc-depth=3'])
            return True
        except Exception as e:
            logger.error("HTML → DOCX 转换失败: %s", e)
            return False

    def _remove_empty_paragraphs(self, docx_path: str):
        doc = Document(docx_path)
        from docx.oxml.ns import qn
        empty = []
        for p in doc.paragraphs:
            has_text = bool(p.text.strip())
            has_pic = bool(p._element.findall('.//' + qn('a:blip')))
            if not has_text and not has_pic:
                empty.append(p)
        for p in reversed(empty):
            p._element.getparent().remove(p._element)
        doc.save(docx_path)
        logger.info("已移除 %d 个空段落", len(empty))
