"""
HTML 交互式报告生成器
将分析结果渲染为美观、可交互的 HTML 文件
"""

import json
from pathlib import Path
from typing import Dict, Any


def generate_html_report(analysis_result: Dict[str, Any], output_path: str | Path) -> None:
    """生成 HTML 报告并保存到指定路径"""
    
    title = analysis_result.get("title", "政策分析报告")
    generated_at = analysis_result.get("generated_at", "")
    audience = analysis_result.get("audience", "通用视角")
    
    # 提取各部分数据
    exec_summary = analysis_result.get("executive_summary", {})
    policy_analysis = analysis_result.get("policy_analysis", {})
    risk_scenarios = analysis_result.get("risk_scenarios", {})
    business_impact = analysis_result.get("business_impact", {})
    
    # 构建 HTML 内容
    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            :root {{
                --bg-color: #f9fafb;
                --text-color: #111827;
                --card-bg: #ffffff;
                --border-color: #e5e7eb;
            }}
            @media (prefers-color-scheme: dark) {{
                :root {{
                    --bg-color: #111827;
                    --text-color: #f9fafb;
                    --card-bg: #1f2937;
                    --border-color: #374151;
                }}
            }}
            body {{
                background-color: var(--bg-color);
                color: var(--text-color);
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                line-height: 1.6;
            }}
            .card {{
                background-color: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 0.5rem;
                padding: 1.5rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
            }}
            .tag {{
                display: inline-block;
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
                font-size: 0.875rem;
                font-weight: 500;
                margin-right: 0.5rem;
                margin-bottom: 0.5rem;
            }}
            .tag-high {{ background-color: #fee2e2; color: #991b1b; }}
            .tag-medium {{ background-color: #fef3c7; color: #92400e; }}
            .tag-low {{ background-color: #e0f2fe; color: #075985; }}
            .tag-F {{ background-color: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }}
            .tag-I {{ background-color: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff; }}
            .tag-S {{ background-color: #ffedd5; color: #c2410c; border: 1px solid #fed7aa; }}
        </style>
    </head>
    <body class="p-4 md:p-8 max-w-5xl mx-auto">
        <header class="mb-8 text-center">
            <h1 class="text-3xl font-bold mb-2">{title}</h1>
            <p class="text-sm text-gray-500 dark:text-gray-400">
                <span class="bg-indigo-100 text-indigo-800 text-xs font-medium mr-2 px-2.5 py-0.5 rounded dark:bg-indigo-900 dark:text-indigo-300">目标受众: {audience}</span>
                生成时间: {generated_at}
            </p>
        </header>

        <!-- 执行摘要 -->
        <section class="card border-l-4 border-l-blue-500">
            <h2 class="text-2xl font-semibold mb-4 text-blue-600 dark:text-blue-400">执行摘要</h2>
            <p class="text-lg font-medium mb-4">{exec_summary.get("one_liner", "")}</p>
            
            <div class="grid md:grid-cols-2 gap-6">
                <div>
                    <h3 class="font-bold mb-2">核心结论</h3>
                    <ul class="list-disc pl-5">
                        {''.join([f"<li>{item}</li>" for item in exec_summary.get("core_conclusions", [])])}
                    </ul>
                </div>
                <div>
                    <h3 class="font-bold mb-2">关键风险</h3>
                    <ul class="list-disc pl-5 text-red-600 dark:text-red-400">
                        {''.join([f"<li>{item}</li>" for item in exec_summary.get("key_risks", [])])}
                    </ul>
                </div>
                <div>
                    <h3 class="font-bold mb-2">行动建议</h3>
                    <ul class="list-disc pl-5 text-green-600 dark:text-green-400">
                        {''.join([f"<li>{item}</li>" for item in exec_summary.get("action_items", [])])}
                    </ul>
                </div>
                <div>
                    <h3 class="font-bold mb-2">观察清单</h3>
                    <ul class="list-disc pl-5 text-purple-600 dark:text-purple-400">
                        {''.join([f"<li>{item}</li>" for item in exec_summary.get("watch_list", [])])}
                    </ul>
                </div>
            </div>
        </section>

        <!-- 深度政策分析 -->
        <section class="card">
            <h2 class="text-2xl font-semibold mb-4">深度政策分析</h2>
            
            <h3 class="text-xl font-bold mb-3 border-b pb-2">核心判断</h3>
            <div class="mb-6 space-y-3">
                {''.join([
                    f'''<div class="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                        <div class="mb-1">
                            <span class="tag tag-{j.get('evidence_type', 'I')}">{j.get('evidence_type', 'I')}</span>
                            <span class="tag tag-{j.get('confidence', 'medium')}">置信度: {j.get('confidence', 'medium')}</span>
                        </div>
                        <p class="font-medium">{j.get('judgment', '')}</p>
                        <p class="text-sm text-gray-500 mt-1">依据: {j.get('evidence', '')}</p>
                    </div>'''
                    for j in policy_analysis.get("core_judgments", [])
                ])}
            </div>

            <div class="grid md:grid-cols-2 gap-6 mb-6">
                <div>
                    <h3 class="text-xl font-bold mb-3 border-b pb-2">政策意图</h3>
                    <p><strong>显性目标:</strong> {', '.join(policy_analysis.get("policy_intent", {}).get("explicit_goals", []))}</p>
                    <p class="mt-2"><strong>隐性目标:</strong> {', '.join(policy_analysis.get("policy_intent", {}).get("implicit_goals", []))}</p>
                    <p class="mt-2 text-gray-600 dark:text-gray-300"><em>政治逻辑: {policy_analysis.get("policy_intent", {}).get("political_logic", "")}</em></p>
                </div>
                <div>
                    <h3 class="text-xl font-bold mb-3 border-b pb-2">制度地图</h3>
                    <p><strong>牵头机构:</strong> {policy_analysis.get("institutional_map", {}).get("lead_agency", "")}</p>
                    <p class="mt-1"><strong>协调机构:</strong> {', '.join(policy_analysis.get("institutional_map", {}).get("coordination_bodies", []))}</p>
                    <p class="mt-1"><strong>执行路径:</strong> {policy_analysis.get("institutional_map", {}).get("execution_path", "")}</p>
                    <p class="mt-1 text-red-600 dark:text-red-400"><strong>潜在堵点:</strong> {', '.join(policy_analysis.get("institutional_map", {}).get("potential_bottlenecks", []))}</p>
                </div>
            </div>
            
            <h3 class="text-xl font-bold mb-3 border-b pb-2">利益影响分析</h3>
            <div class="grid md:grid-cols-2 gap-4">
                <div class="bg-green-50 dark:bg-green-900/20 p-3 rounded border border-green-200 dark:border-green-800">
                    <h4 class="font-bold text-green-700 dark:text-green-400">👍 受益方</h4>
                    <ul class="list-disc pl-5 mt-2">
                        {''.join([
                            f"<li><strong>{w.get('entity', '')}</strong> ({w.get('timeline', '')})<br><span class='text-sm text-gray-600 dark:text-gray-400'>{w.get('reason', '')}</span></li>"
                            for w in policy_analysis.get("stakeholder_impact", {}).get("winners", [])
                        ])}
                    </ul>
                </div>
                <div class="bg-red-50 dark:bg-red-900/20 p-3 rounded border border-red-200 dark:border-red-800">
                    <h4 class="font-bold text-red-700 dark:text-red-400">👎 受损方</h4>
                    <ul class="list-disc pl-5 mt-2">
                        {''.join([
                            f"<li><strong>{l.get('entity', '')}</strong> ({l.get('timeline', '')})<br><span class='text-sm text-gray-600 dark:text-gray-400'>{l.get('reason', '')}</span></li>"
                            for l in policy_analysis.get("stakeholder_impact", {}).get("losers", [])
                        ])}
                    </ul>
                </div>
            </div>
        </section>

        <!-- 风险情景分析 -->
        <section class="card">
            <h2 class="text-2xl font-semibold mb-4 text-orange-600 dark:text-orange-400">风险情景分析</h2>
            
            <div class="space-y-4 mb-6">
                {''.join([
                    f'''<div class="border rounded p-4 border-l-4 {
                        'border-l-blue-500' if s.get('type') == 'baseline' else 
                        'border-l-green-500' if s.get('type') == 'optimistic' else 
                        'border-l-yellow-500' if s.get('type') == 'pessimistic' else 
                        'border-l-red-500'
                    }">
                        <div class="flex justify-between items-center mb-2">
                            <h3 class="font-bold text-lg">{s.get('name', '')} ({s.get('type', '')})</h3>
                            <span class="font-mono bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">概率: {s.get('probability', '')}</span>
                        </div>
                        <p class="mb-2"><strong>触发条件:</strong> {', '.join(s.get('trigger_conditions', []))}</p>
                        <p class="mb-2"><strong>发展路径:</strong> {s.get('development_path', '')}</p>
                        <p><strong>影响评估:</strong> {s.get('impact', '')}</p>
                    </div>'''
                    for s in risk_scenarios.get("scenarios", [])
                ])}
            </div>
        </section>

        <!-- 商业/合规影响 -->
        <section class="card">
            <h2 class="text-2xl font-semibold mb-4 text-purple-600 dark:text-purple-400">商业与合规影响</h2>
            
            <div class="grid md:grid-cols-2 gap-6">
                <div>
                    <h3 class="text-xl font-bold mb-3 border-b pb-2">合规风险提示</h3>
                    <ul class="space-y-3">
                        {''.join([
                            f'''<li class="bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded">
                                <p class="font-bold text-yellow-800 dark:text-yellow-400">{r.get('risk', '')}</p>
                                <p class="text-sm mt-1">影响主体: {', '.join(r.get('affected_entities', []))}</p>
                                <p class="text-sm mt-1">缓解措施: {r.get('mitigation', '')}</p>
                            </li>'''
                            for r in business_impact.get("compliance_risks", [])
                        ])}
                    </ul>
                </div>
                <div>
                    <h3 class="text-xl font-bold mb-3 border-b pb-2">行动建议方案</h3>
                    <ul class="space-y-3">
                        {''.join([
                            f'''<li class="bg-indigo-50 dark:bg-indigo-900/20 p-3 rounded">
                                <div class="flex justify-between items-start mb-1">
                                    <p class="font-bold text-indigo-800 dark:text-indigo-400">{a.get('action', '')}</p>
                                    <span class="text-xs bg-indigo-100 dark:bg-indigo-800 px-1 py-0.5 rounded">{a.get('urgency', '')}</span>
                                </div>
                                <p class="text-sm mt-1 text-gray-600 dark:text-gray-400">{a.get('rationale', '')}</p>
                            </li>'''
                            for a in business_impact.get("action_items", [])
                        ])}
                    </ul>
                </div>
            </div>
        </section>

        <footer class="text-center text-sm text-gray-500 mt-8 mb-4">
            <p>AI 政策解读程序生成 | {generated_at}</p>
        </footer>
    </body>
    </html>
    """
    
    # 写入文件
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(html_content, encoding="utf-8")
