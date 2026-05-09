"""
政策分析编排器
按照 5 个阶段依次调用 LLM 完成多维度政策分析
"""

import json
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timezone

from core.llm_client import LLMClient
from core.prompts import (
    SYSTEM_PROMPT,
    MATERIAL_UNDERSTANDING_PROMPT,
    POLICY_ANALYSIS_PROMPT,
    RISK_SCENARIO_PROMPT,
    BUSINESS_IMPACT_PROMPT,
    EXECUTIVE_SUMMARY_PROMPT,
)
from config import LLM_MODEL

logger = logging.getLogger(__name__)

# 分析阶段定义
ANALYSIS_STAGES = [
    {"name": "材料理解", "progress": 15},
    {"name": "深度政策分析", "progress": 40},
    {"name": "风险情景分析", "progress": 60},
    {"name": "商业影响分析", "progress": 80},
    {"name": "生成执行摘要", "progress": 95},
    {"name": "完成", "progress": 100},
]


async def analyze_policy(
    content: str,
    progress_callback: Optional[Callable] = None,
    audience: str = "通用视角",
) -> Dict[str, Any]:
    """
    执行完整的政策分析流程

    参数:
        content: 政策文件文本内容
        progress_callback: 进度回调函数 (stage_name, progress, message)

    返回:
        完整的分析结果字典
    """
    client = LLMClient()

    def _report(stage: str, progress: int, message: str):
        """上报进度"""
        logger.info(f"[{stage}] {message}")
        if progress_callback:
            progress_callback(stage, progress, message)

    try:
        # ============================================================
        # 阶段 1: 材料理解
        # ============================================================
        _report("材料理解", 10, "正在识别材料类型和关键信息...")

        material_understanding = await client.chat_json(
            prompt=MATERIAL_UNDERSTANDING_PROMPT.format(content=content[:8000]),
            system_prompt=SYSTEM_PROMPT.format(audience=audience),
            temperature=0.3,
        )

        _report("材料理解", 15, f"识别完成: {material_understanding.get('title', '未知标题')}")

        # ============================================================
        # 阶段 2: 深度政策分析
        # ============================================================
        _report("深度政策分析", 20, "正在进行多维度深度分析...")

        # 对长文档进行压缩
        material_for_analysis = content
        if len(content) > 8000:
            understanding_json = json.dumps(material_understanding, ensure_ascii=False, indent=2)
            material_for_analysis = (
                f"## 材料理解摘要\n{understanding_json}\n\n"
                f"## 原文节选（前8000字）\n{content[:8000]}...\n\n"
                f"[全文共 {len(content)} 字，已截断。核心信息见上方材料理解摘要。]"
            )

        policy_analysis = await client.chat_json(
            prompt=POLICY_ANALYSIS_PROMPT.format(
                content=material_for_analysis,
                material_understanding=json.dumps(material_understanding, ensure_ascii=False, indent=2),
            ),
            system_prompt=SYSTEM_PROMPT.format(audience=audience),
            temperature=0.5,
        )

        _report("深度政策分析", 40, "深度分析完成")

        # ============================================================
        # 阶段 3: 风险情景分析
        # ============================================================
        _report("风险情景分析", 45, "正在构建风险情景...")

        risk_scenarios = await client.chat_json(
            prompt=RISK_SCENARIO_PROMPT.format(
                policy_analysis=json.dumps(policy_analysis, ensure_ascii=False, indent=2),
            ),
            system_prompt=SYSTEM_PROMPT.format(audience=audience),
            temperature=0.6,
        )

        _report("风险情景分析", 60, "风险情景分析完成")

        # ============================================================
        # 阶段 4: 商业/合规影响分析
        # ============================================================
        _report("商业影响分析", 65, "正在分析商业和合规影响...")

        business_impact = await client.chat_json(
            prompt=BUSINESS_IMPACT_PROMPT.format(
                policy_analysis=json.dumps(policy_analysis, ensure_ascii=False, indent=2),
                audience=audience,
            ),
            system_prompt=SYSTEM_PROMPT.format(audience=audience),
            temperature=0.5,
        )

        _report("商业影响分析", 80, "商业影响分析完成")

        # ============================================================
        # 阶段 5: 执行摘要
        # ============================================================
        _report("生成执行摘要", 85, "正在生成执行摘要...")

        full_analysis = {
            "policy_analysis": policy_analysis,
            "risk_scenarios": risk_scenarios,
            "business_impact": business_impact,
        }

        executive_summary = await client.chat_json(
            prompt=EXECUTIVE_SUMMARY_PROMPT.format(
                full_analysis=json.dumps(full_analysis, ensure_ascii=False, indent=2),
            ),
            system_prompt=SYSTEM_PROMPT.format(audience=audience),
            temperature=0.4,
        )

        _report("生成执行摘要", 95, "执行摘要生成完成")

        # ============================================================
        # 组装最终结果
        # ============================================================
        title = material_understanding.get("title", "政策分析报告")
        publish_date = material_understanding.get("publish_date", "")
        if publish_date and publish_date != "未标注":
            analysis_title = f"{publish_date} 《{title}》解读"
        else:
            analysis_title = f"《{title}》解读"

        result = {
            "title": analysis_title,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "llm_model": LLM_MODEL,
            "audience": audience,
            "material_length": len(content),
            "token_usage": client.total_tokens,

            # 各阶段分析结果
            "material_understanding": material_understanding,
            "policy_analysis": policy_analysis,
            "risk_scenarios": risk_scenarios,
            "business_impact": business_impact,
            "executive_summary": executive_summary,
        }

        _report("完成", 100, "分析全部完成")

        return result

    except Exception as e:
        logger.exception(f"政策分析失败: {e}")
        raise
    finally:
        await client.close()
