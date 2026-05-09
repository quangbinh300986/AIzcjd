"""
LLM 统一调用客户端
支持 OpenAI 兼容 API（OpenAI / DeepSeek / 通义千问等）
"""

import json
import aiohttp
from typing import Optional, Dict, Any
from dataclasses import dataclass

from config import LLM_API_KEY, LLM_API_URL, LLM_MODEL


@dataclass
class LLMConfig:
    """LLM 配置"""
    api_key: str = ""
    api_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 8192
    timeout: int = 180


class LLMClient:
    """
    LLM 统一调用客户端

    用法:
        client = LLMClient()
        result = await client.chat("请分析这份政策文件...")
        await client.close()
    """

    def __init__(self, config: Optional[LLMConfig] = None):
        if config:
            self.config = config
        else:
            self.config = LLMConfig(
                api_key=LLM_API_KEY,
                api_url=LLM_API_URL,
                model=LLM_MODEL,
            )
        self._session: Optional[aiohttp.ClientSession] = None
        # Token 用量追踪
        self.total_tokens: int = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def chat(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
    ) -> str:
        """
        发送聊天请求并返回文本响应

        参数:
            prompt: 用户提示词
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大输出 token 数
            response_format: 响应格式 ("json" 启用 JSON 模式)

        返回:
            LLM 生成的文本
        """
        session = await self._get_session()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        # JSON 模式
        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        url = f"{self.config.api_url.rstrip('/')}/chat/completions"

        async with session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"LLM API 调用失败 (HTTP {resp.status}): {error_text}")

            data = await resp.json()

            # 追踪 Token 用量
            usage = data.get("usage", {})
            self.total_tokens += usage.get("total_tokens", 0)

            # 提取响应文本
            choices = data.get("choices", [])
            if not choices:
                raise Exception("LLM 返回了空的 choices")

            return choices[0]["message"]["content"]

    async def chat_json(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        发送聊天请求并解析 JSON 响应

        返回:
            解析后的 JSON 字典
        """
        text = await self.chat(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format="json",
        )

        # 尝试从响应中提取 JSON
        text = text.strip()

        # 如果被 ```json ... ``` 包裹，提取内部内容
        if text.startswith("```"):
            lines = text.split("\n")
            # 移除第一行和最后一行的 ``` 标记
            start = 1
            end = len(lines) - 1
            if lines[end].strip() == "```":
                text = "\n".join(lines[start:end])
            else:
                text = "\n".join(lines[start:])

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试更宽松的提取：查找第一个 { 和最后一个 }
            first_brace = text.find("{")
            last_brace = text.rfind("}")
            if first_brace != -1 and last_brace != -1:
                json_str = text[first_brace:last_brace + 1]
                return json.loads(json_str)
            raise Exception(f"无法解析 LLM 返回的 JSON:\n{text[:500]}")

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
