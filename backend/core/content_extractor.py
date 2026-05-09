"""
多源内容提取器
支持从 URL、PDF 文件、纯文本中提取政策内容
"""

import io
import logging
from pathlib import Path
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


async def extract_from_url(url: str, timeout: int = 30) -> str:
    """
    从 URL 提取网页正文内容

    参数:
        url: 网页 URL
        timeout: 请求超时时间（秒）

    返回:
        提取的正文文本
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("请安装 beautifulsoup4: uv add beautifulsoup4")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    client_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        async with session.get(url, headers=headers, ssl=False) as resp:
            if resp.status != 200:
                raise Exception(f"URL 请求失败 (HTTP {resp.status}): {url}")

            html = await resp.text()

    soup = BeautifulSoup(html, "lxml")

    # 移除无关标签
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe"]):
        tag.decompose()

    # 尝试提取正文区域（常见的政府网站正文容器）
    content_selectors = [
        "article",
        ".article-content",
        ".content",
        "#content",
        ".TRS_Editor",     # 政府网站常用
        ".pages_content",  # 中国政府网
        ".text",
        "main",
        ".main-content",
    ]

    text = ""
    for selector in content_selectors:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator="\n", strip=True)
            if len(text) > 100:
                break

    # 如果没有找到正文容器，使用 body 全文
    if len(text) < 100:
        body = soup.find("body")
        if body:
            text = body.get_text(separator="\n", strip=True)

    # 清理：去除连续空行
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    # 提取标题
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    if title:
        text = f"标题: {title}\n来源: {url}\n\n{text}"

    return text


def extract_from_pdf(file_path: str) -> str:
    """
    从 PDF 文件提取文本内容

    参数:
        file_path: PDF 文件路径

    返回:
        提取的文本内容
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("请安装 pdfplumber: uv add pdfplumber")

    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n\n".join(text_parts)


def extract_from_pdf_bytes(content: bytes) -> str:
    """
    从 PDF 字节流提取文本内容

    参数:
        content: PDF 文件的字节内容

    返回:
        提取的文本内容
    """
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("请安装 pdfplumber: uv add pdfplumber")

    text_parts = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    return "\n\n".join(text_parts)


def extract_from_text(text: str) -> str:
    """
    清理纯文本内容

    参数:
        text: 原始文本

    返回:
        清理后的文本
    """
    # 去除首尾空白
    text = text.strip()
    # 去除连续空行（保留最多一个空行）
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


async def extract_content(
    url: Optional[str] = None,
    file_path: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    file_type: Optional[str] = None,
    text: Optional[str] = None,
) -> str:
    """
    统一内容提取入口

    参数:
        url: 网页 URL
        file_path: 文件路径
        file_bytes: 文件字节内容
        file_type: 文件类型 (pdf/text)
        text: 纯文本内容

    返回:
        提取的文本内容
    """
    if url:
        logger.info(f"正在从 URL 提取内容: {url}")
        return await extract_from_url(url)

    if file_path:
        path = Path(file_path)
        if path.suffix.lower() == ".pdf":
            logger.info(f"正在从 PDF 提取内容: {file_path}")
            return extract_from_pdf(file_path)
        else:
            logger.info(f"正在从文本文件提取内容: {file_path}")
            return extract_from_text(path.read_text(encoding="utf-8", errors="ignore"))

    if file_bytes and file_type:
        if file_type == "pdf":
            logger.info("正在从 PDF 字节流提取内容")
            return extract_from_pdf_bytes(file_bytes)
        else:
            logger.info("正在从文本字节流提取内容")
            return extract_from_text(file_bytes.decode("utf-8", errors="ignore"))

    if text:
        return extract_from_text(text)

    raise ValueError("必须提供 url、file_path、file_bytes 或 text 中的至少一个参数")
