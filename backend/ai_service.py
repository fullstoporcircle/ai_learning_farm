import os
import json
import re
import logging
import time
import random
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# 确保 .env 被加载（在读取环境变量之前）
from dotenv import load_dotenv
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_load_result = load_dotenv(_env_path, override=True)
print("=" * 60)
print("[DIAG] ai_service.py: load_dotenv result =", _load_result)
print("[DIAG] ai_service.py: .env path =", _env_path)
print("[DIAG] ai_service.py: .env file exists =", os.path.isfile(_env_path))
print("=" * 60)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")
USE_FALLBACK = os.getenv("USE_FALLBACK", "True").lower() == "true"

print("=" * 60)
print("=== AI Service Config (STARTUP) ===")
print(f"  USE_FALLBACK = {USE_FALLBACK}")
print(f"  DEEPSEEK_API_KEY exists = {bool(DEEPSEEK_API_KEY)}")
print(f"  DEEPSEEK_API_KEY prefix = {DEEPSEEK_API_KEY[:8] + '...' if DEEPSEEK_API_KEY and len(DEEPSEEK_API_KEY) > 8 else 'N/A'}")
print(f"  MODEL_NAME = {MODEL_NAME}")
print("=" * 60)

MAX_PROMPT_LEN = int(os.getenv("MAX_PROMPT_LEN", "6000"))
SUMMARY_THRESHOLD = int(os.getenv("SUMMARY_THRESHOLD", "4000"))
ENABLE_SUMMARY_COMPRESS = os.getenv("ENABLE_SUMMARY_COMPRESS", "True").lower() == "true"


def summarize_long_text(text: str, target_length: int = 400) -> str:
    """
    使用 DeepSeek 模型对长文本进行摘要压缩，保留全部关键信息。
    若摘要失败或未启用压缩，返回截断后的文本。

    Args:
        text: 原始长文本
        target_length: 目标摘要长度（字符数），默认 400

    Returns:
        压缩后的文本（摘要或截断）
    """
    original_len = len(text)
    if original_len <= SUMMARY_THRESHOLD or not ENABLE_SUMMARY_COMPRESS:
        return text

    try:
        summary_prompt = (
            f"请将以下对话压缩成 {target_length} 字以内的摘要，保留所有提到的概念、问题、结论和例子。"
            "不要遗漏任何关键知识点。\n"
            f"对话内容：{text}\n摘要："
        )
        result = _call_deepseek(
            summary_prompt,
            system_prompt="你是一个文本摘要专家，擅长在极短篇幅内保留所有关键知识点。",
            max_tokens=target_length * 2,
            temperature=0.3,
        )
        logger.info("文本已摘要压缩: %d -> %d 字符", original_len, len(result))
        return result
    except Exception as e:
        logger.warning("摘要压缩失败，回退到截断逻辑: %s", e)

    MAX_SAFE = MAX_PROMPT_LEN
    if len(text) > MAX_SAFE:
        text = text[:MAX_SAFE]
        logger.warning("摘要压缩失败，文本已截断至 %d 字符", MAX_SAFE)
    return text


DEFAULT_MESSAGES = [
    "种下的种子正在发芽，继续浇水哦！",
    "掌握一个难点，比背十个公式更有价值~",
    "今天的努力，明天的收获！加油！",
    "学习就像种地，用心就会有成果~",
    "每天进步一点点，积少成多！",
    "遇到难题别放弃，我陪你一起攻克！",
    "你的知识农场正在茁壮成长！",
    "坚持就是胜利，你已经很棒了！",
    "劳逸结合，学习效率更高哦~",
    "今天也要元气满满地学习呀！",
    "知识的果实就在前方，继续加油！",
    "你的努力值得被看见，继续前进！",
    "小步快跑，每天都有新收获~",
    "学习是一场马拉松，坚持下去！",
    "每一次浇水都是在浇灌智慧的种子！"
]

DOMAIN_TEMPLATES = {
    "通用": {
        "explain": "请详细解释 {title} 的定义，并给出一个典型例子。",
        "apply": "请举例说明 {title} 在实际场景中的应用。",
        "compare": "请比较 {title} 与相关概念的异同。",
        "relation": "请描述 {title} 与其他相关概念之间的关系。",
        "critique": "请分析 {title} 的局限性或适用边界条件。",
        "synthesis": "请将 {title} 与相关概念结合，解决一个综合问题。",
        "evaluate": "请评估关于 {title} 的以下论述的可靠性：{content}",
        "summarize": "请用简洁的语言总结 {title} 的核心要点。"
    },
    "人工智能": {
        "explain": "请详细解释 {title} 的原理，并说明其在AI系统中的作用。",
        "apply": "请设计一个使用 {title} 解决实际问题的方案。",
        "compare": "请比较 {title} 与其他相关AI技术的优缺点。",
        "debug": "以下代码实现 {title} 时可能存在什么问题？如何修复？",
        "critique": "请分析 {title} 的理论假设、局限性及适用边界。",
        "synthesis": "请将 {title} 与注意力机制结合，设计一个改进方案。",
        "evaluate": "请评估以下关于 {title} 的研究结论的可靠性。",
        "summarize": "请总结 {title} 的核心思想和技术要点。"
    },
    "经济学": {
        "explain": "请解释 {title} 的核心概念和主要理论。",
        "apply": "请分析 {title} 在现实经济生活中的应用。",
        "compare": "请比较 {title} 与其他经济理论的异同。",
        "relation": "请描述 {title} 与市场机制之间的关系。",
        "critique": "请批判性分析 {title} 的理论假设和现实局限性。",
        "synthesis": "请将 {title} 与行为经济学结合，分析一个实际案例。",
        "evaluate": "请评估关于 {title} 的实证研究结论的可靠性。",
        "summarize": "请总结 {title} 的理论框架和政策含义。"
    },
    "工程学": {
        "explain": "请解释 {title} 的工作原理和技术要点。",
        "apply": "请设计一个基于 {title} 的工程解决方案。",
        "compare": "请比较 {title} 与相关工程方法的优劣。",
        "calc": "请计算在给定条件下 {title} 的性能参数。",
        "critique": "请分析 {title} 的技术局限性和改进方向。",
        "synthesis": "请将 {title} 与现代优化方法结合，提出改进方案。",
        "evaluate": "请评估使用 {title} 的工程方案的风险和收益。",
        "summarize": "请总结 {title} 的关键技术指标和应用场景。"
    },
    "理学": {
        "explain": "请详细解释 {title} 的科学原理和实验依据。",
        "apply": "请举例说明 {title} 在科学研究中的应用。",
        "compare": "请对比 {title} 与相关理论的异同。",
        "calc": "请推导 {title} 相关的核心公式。",
        "critique": "请分析 {title} 理论的假设条件和适用范围。",
        "synthesis": "请将 {title} 与其他理论结合，解释一个复杂现象。",
        "evaluate": "请评估支持 {title} 的实验证据的可靠性。",
        "summarize": "请总结 {title} 的核心原理和主要结论。"
    },
    "哲学": {
        "explain": "请解释 {title} 的核心观点和论证方式。",
        "apply": "请分析 {title} 对当代社会的启示。",
        "compare": "请比较 {title} 与其他哲学流派的异同。",
        "relation": "请描述 {title} 与认识论之间的关系。",
        "critique": "请批判性分析 {title} 的论证逻辑和潜在问题。",
        "synthesis": "请将 {title} 与现代科学观点结合进行讨论。",
        "evaluate": "请评估 {title} 论证的有效性和说服力。",
        "summarize": "请总结 {title} 的核心论点和哲学意义。"
    },
    "管理学": {
        "explain": "请解释 {title} 的基本概念和管理学意义。",
        "apply": "请分析如何在实际管理中运用 {title}。",
        "compare": "请比较 {title} 与其他管理方法的适用场景。",
        "relation": "请描述 {title} 与组织绩效之间的关系。",
        "critique": "请分析 {title} 的适用条件和潜在局限性。",
        "synthesis": "请将 {title} 与数字化管理结合，提出创新方案。",
        "evaluate": "请评估 {title} 在特定组织环境中的有效性。",
        "summarize": "请总结 {title} 的管理原则和实践要点。"
    }
}

try:
    from openai import OpenAI
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com/v1") if DEEPSEEK_API_KEY and not USE_FALLBACK else None
    print(f"[DIAG] OpenAI client initialized: {client is not None}")
    if client is None:
        print(f"[DIAG] client=None because: DEEPSEEK_API_KEY={bool(DEEPSEEK_API_KEY)}, USE_FALLBACK={USE_FALLBACK}")
except ImportError as ie:
    print(f"[DIAG] openai library import FAILED: {ie}")
    logger.warning("openai library not installed, falling back to mock mode")
    client = None


def _call_deepseek(prompt: str, system_prompt: str = "You are a helpful assistant.", 
                   temperature: float = 0.5, json_mode: bool = False,
                   max_tokens: Optional[int] = None) -> str:
    """
    调用 DeepSeek API，支持 JSON 模式，处理降级和重试。
    """
    logger.debug(f"[DEBUG] _call_deepseek called, USE_FALLBACK={USE_FALLBACK}, client={client is not None}")
    print(f"[DIAG] _call_deepseek called, USE_FALLBACK={USE_FALLBACK}, client={client is not None}")
    
    if client is None or USE_FALLBACK:
        print(f"[DIAG] Using FALLBACK mode (client={client is not None}, USE_FALLBACK={USE_FALLBACK})")
        logger.info("[DEBUG] Using FALLBACK mode (client=%s, USE_FALLBACK=%s)", client is not None, USE_FALLBACK)
        return _fallback_response(prompt)
    
    print(f"[DIAG] Using REAL DeepSeek API (model={MODEL_NAME})")
    logger.info("[DEBUG] Using REAL DeepSeek API (model=%s)", MODEL_NAME)
    
    max_retries = 2
    retry_delay = 0.5
    
    for attempt in range(max_retries):
        try:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
            kwargs = {
                "model": MODEL_NAME,
                "messages": messages,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens
            
            response = client.chat.completions.create(**kwargs)
            result = response.choices[0].message.content
            
            if result and result.strip():
                return result
            
            logger.warning(f"DeepSeek API 返回空内容，尝试重试 ({attempt + 1}/{max_retries})")
            
        except Exception as e:
            logger.error(f"DeepSeek API 调用失败 (尝试 {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    
    logger.error("DeepSeek API 多次调用失败")
    if USE_FALLBACK:
        return _fallback_response(prompt)
    raise RuntimeError("DeepSeek API 调用失败，已达到最大重试次数")


def _extract_keywords_from_text(text: str, max_keywords: int = 3) -> list:
    """从文本中提取关键词（简单实现：优先提取4字词组，再取3字、2字）"""
    chinese_segments = re.findall(r'[\u4e00-\u9fff]+', text)
    all_words = []
    seen = set()
    for segment in chinese_segments:
        for length in [4, 3, 2]:
            for i in range(len(segment) - length + 1):
                word = segment[i:i+length]
                if word not in seen and len(word) >= 2:
                    seen.add(word)
                    all_words.append(word)
    stop_words = {'的是', '一个', '我们', '他们', '这些', '那些', '这个', '那个',
                  '可以', '因为', '所以', '如果', '那么', '或者', '但是', '而且',
                  '不是', '就是', '已经', '正在', '通过', '进行', '使用', '包括',
                  '以及', '其中', '对于', '关于', '之间', '之后', '之前', '以上',
                  '以下', '其他', '一些', '一种', '这个', '那个', '什么', '怎么',
                  '如何', '为什么', '怎样', '哪些', '多少', '几个', '没有', '能够',
                  '应该', '需要', '必须', '可能', '大概', '也许', '一定', '确实'}
    filtered = [w for w in all_words if w not in stop_words]
    return filtered[:max_keywords] if filtered else ["知识点"]


def _fallback_response(prompt: str) -> str:
    """
    根据prompt特征和内容动态返回模拟响应。
    尽可能从输入中提取信息，而非返回硬编码数据。
    """
    prompt_lower = prompt.lower()
    
    if "extract_knowledge" in prompt_lower or "知识点提取" in prompt or "提取" in prompt:
        dialog_match = re.search(r'对话内容[：:]\s*\n(.+?)(?:\n\n|$)', prompt, re.DOTALL)
        dialog_text = dialog_match.group(1).strip() if dialog_match else prompt
        keywords = _extract_keywords_from_text(dialog_text)
        main_keyword = keywords[0] if keywords else "知识点"
        secondary_keyword = keywords[1] if len(keywords) > 1 else "相关概念"
        third_keyword = keywords[2] if len(keywords) > 2 else "应用"
        
        return json.dumps([
            {
                "title": f"{main_keyword}的核心定义",
                "content": f"{main_keyword}是一个重要的概念。核心定义：{main_keyword}指的是在特定领域中具有关键作用的理论或方法。核心原理：{main_keyword}通过其内在机制影响相关系统的运行，理解其本质需要掌握其基本要素和运作方式。例子：在实际应用中，{main_keyword}的一个典型场景是在{secondary_keyword}领域中的运用，例如通过{third_keyword}来验证其有效性。注意：初学者常将{main_keyword}与表面相似的概念混淆，需要仔细区分其本质特征。",
                "type": "concept",
                "difficulty": 0.5,
                "tags": [secondary_keyword, main_keyword, third_keyword],
                "domain": "通用",
                "depth": "intermediate",
                "formula": "",
                "derivation_steps": [],
                "common_mistakes": [f"容易将{main_keyword}与{secondary_keyword}混淆", f"忽略{main_keyword}的适用条件"],
                "application_examples": [f"在{secondary_keyword}领域的典型应用", f"{main_keyword}在{third_keyword}中的实践"]
            },
            {
                "title": f"{main_keyword}与{secondary_keyword}的关系",
                "content": f"{main_keyword}与{secondary_keyword}之间存在密切的关联。核心原理：{main_keyword}是{secondary_keyword}的基础或前提条件，理解两者关系有助于构建完整的知识体系。例子：当{main_keyword}发生变化时，{secondary_keyword}也会相应调整，这种联动关系在实际问题中经常出现。注意：不能孤立地理解{main_keyword}，需要放在{secondary_keyword}的背景下综合考虑。",
                "type": "fact",
                "difficulty": 0.3,
                "tags": [main_keyword, secondary_keyword],
                "domain": "通用",
                "depth": "basic",
                "formula": "",
                "derivation_steps": [],
                "common_mistakes": [f"孤立理解{main_keyword}而忽略其与{secondary_keyword}的联系"],
                "application_examples": [f"分析{main_keyword}对{secondary_keyword}的影响"]
            }
        ])
    
    elif "摘要" in prompt or "压缩" in prompt:
        keywords = _extract_keywords_from_text(prompt)
        return f"本对话讨论了{keywords[0] if keywords else '多个'}核心概念，包括基本定义、原理分析和应用场景。主要涉及的关键知识点有：概念的定义与特征、核心原理的推导过程、实际应用中的典型例子，以及相关理论的局限性分析。"
    
    elif "复习卡片" in prompt or "fact_card" in prompt_lower:
        title_match = re.search(r'标题[：:]\s*(.+)', prompt)
        content_match = re.search(r'内容[：:]\s*(.+)', prompt)
        title = title_match.group(1).strip() if title_match else "知识点"
        content = content_match.group(1).strip()[:100] if content_match else "核心内容"
        return json.dumps({
            "title": title,
            "content": content,
            "hint": f"请回忆「{title}」的核心内容是什么？",
            "example": f"结合实际场景想一想：{title}在生活中的体现"
        })
    
    elif "评分" in prompt_lower or "evaluate" in prompt_lower or "评估" in prompt:
        answer_match = re.search(r'用户回答[：:]\s*(.+)', prompt, re.DOTALL)
        answer_text = answer_match.group(1).strip()[:50] if answer_match else ""
        answer_len = len(answer_text)
        score = min(0.8, max(0.3, answer_len / 200))
        return json.dumps({
            "score": round(score, 2),
            "correct_parts": ["回答了部分核心内容"] if answer_len > 10 else [],
            "missing_parts": ["缺少公式或具体推导", "未给出计算例子", "需要更详细的解释"],
            "mistakes": [] if answer_len > 30 else ["回答过于简略"],
            "correct_derivation": "正确的推导思路：首先明确概念定义，然后写出核心公式，接着代入具体数值进行计算演示，最后总结注意事项和常见误解。",
            "reference_answer": "完整的参考答案应包含：1) 核心定义；2) 公式或原理；3) 具体计算例子；4) 注意事项和常见误解。",
            "further_study": ["相关概念的深入学习", "更多练习题"]
        })
    
    elif "generate_concept_question" in prompt_lower or "出题" in prompt:
        title_match = re.search(r'标题[：:]\s*(.+)', prompt) or re.search(r'概念[：:]\s*(.+)', prompt)
        title = title_match.group(1).strip() if title_match else "知识点"
        return json.dumps({
            "question_text": f"请详细解释「{title}」的核心原理，并举例说明其应用场景。",
            "verify_type": "explain"
        })
    
    elif "classify" in prompt_lower or "分类" in prompt:
        return "concept"
    
    else:
        keywords = _extract_keywords_from_text(prompt)
        return json.dumps({
            "result": "success",
            "data": f"关于{keywords[0] if keywords else '该问题'}的模拟响应"
        })


def extract_knowledge_from_conversation(conversation_text: str) -> List[Dict[str, Any]]:
    """
    从对话文本中提取知识点。长对话优先使用摘要压缩，仅在摘要后仍超限时截断。
    """
    logger.info("[DEBUG] extract_knowledge called, text preview: %s", conversation_text[:100])
    print(f"[DIAG] extract_knowledge called, text preview: {conversation_text[:100]}...")
    print(f"[DIAG] extract_knowledge: text length={len(conversation_text)}, USE_FALLBACK={USE_FALLBACK}")
    original_len = len(conversation_text)

    if original_len > SUMMARY_THRESHOLD and ENABLE_SUMMARY_COMPRESS:
        conversation_text = summarize_long_text(conversation_text, target_length=400)
        if len(conversation_text) < original_len:
            logger.info("对话已摘要压缩: %d -> %d 字符", original_len, len(conversation_text))

    if len(conversation_text) > MAX_PROMPT_LEN:
        conversation_text = conversation_text[:MAX_PROMPT_LEN]
        logger.warning("对话文本过长，已截断至 %d 字符", MAX_PROMPT_LEN)

    prompt = f"""从以下对话中提取具体的学科知识点。输出一个 JSON 数组，每个元素包含：
- title: 简短标题（10字内）
- content: 核心解释（50-100字）
- difficulty: 0~1 浮点数（简单=0.3，中等=0.6，困难=0.9）
- tags: 字符串数组（2-4个标签）

【严禁提取的内容类型（无条件过滤）】
以下内容属于"课程元信息"，不是学科知识，必须跳过：
- 课程结构描述：课程目标、适用人群、学习方法、课程大纲、章节安排、学前准备
- 教学计划/进度信息：教学进度、课时分配、学习安排、考核方式
- 过渡/引导语句："本视频会介绍"、"接下来我们将学习"、"前面我们讲了"
- 纯鼓励性/号召性语句："坚持学习"、"加油"、"每天进步"、"关注收藏"
- 列表索引/编号（无实际知识内容）："前缀第1-5个"、"共12个前缀"
- 考试/等级/证书相关信息：考研要求、四级词汇量、考试技巧、备考策略
- 讲师个人介绍、视频制作说明、背景故事（与学科无关的部分）

【知识点准入标准（必须同时满足）】
每个提取的知识点必须满足以下全部条件：
1. 可定义性：它能被一句话定义"XX是什么"
2. 可解释性：能用50-100字清晰解释其含义、原理或用法
3. 可应用性：可以用于解决实际问题或回答相关题目
4. 独立性：脱离原视频/课程上下文后仍可独立理解
5. 学科性：属于某个明确学科领域（语言、数学、编程、物理、历史、化学等）

【Few-shot 示例 —— 好的知识点 ✅】
- "词根 'ex-' 表示向外、出" ✅ (可定义、可解释、可应用)
- "梯度下降是一种通过迭代更新参数来最小化损失函数的优化算法" ✅
- "牛顿第一定律：物体在不受外力时保持静止或匀速直线运动" ✅
- "Python装饰器是接受函数为参数并返回新函数的高阶函数" ✅
- "HTTP状态码200表示成功，404表示未找到，500表示服务器错误" ✅

【Few-shot 示例 —— 不好的知识点 ❌ 必须跳过】
- "课程目标：掌握12大前缀" ❌ (课程元信息)
- "适用人群：英语学习者" ❌ (课程元信息)
- "学习方法：每天背诵5个词根" ❌ (学习建议)
- "本视频将介绍词根词缀法" ❌ (课程介绍)
- "前缀第1-5个：ex-, pre-, re-, un-, dis-" ❌ (纯列表无解释)
- "英语四级需要掌握40个词根" ❌ (考试要求)
- "坚持学习，你一定可以掌握" ❌ (鼓励语句)

如果对话中确实没有可提取的学科知识（或只有课程元信息），直接输出空数组 []

对话内容：
{conversation_text}

只输出 JSON 数组，不要有其他文字。示例：
[{{"title": "contains()方法", "content": "C++20无序容器引入contains()判断键存在，返回bool，比find()更简洁。", "difficulty": 0.4, "tags": ["C++", "容器"]}}]"""

    try:
        response = _call_deepseek(
            prompt,
            system_prompt="你是学科知识提取助手，只提取可定义、可解释、可应用且独立于课程上下文的学科知识点（定义/公式/原理/代码/算法/事实）。严禁提取课程目标、适用人群、学习方法、课程大纲、章节安排、考试要求、鼓励语句、纯列表索引元信息等。若无可提取的学科知识则输出空数组。",
            temperature=0.3,
            json_mode=True,
            max_tokens=400,
        )
        cleaned = response.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned)
        if isinstance(result, list):
            filtered = []
            for item in result:
                if 'tags' not in item:
                    item['tags'] = []
                title = item.get('title', '')
                content = item.get('content', '')
                combined = title + content
                if _is_forbidden(combined):
                    logger.info("过滤非学科知识点: title=%s", title)
                    continue
                filtered.append(item)
            return filtered
        return []
    except Exception as e:
        logger.error(f"知识点提取失败: {e}")
        return _mock_knowledge_extraction(conversation_text)


FORBIDDEN_PATTERNS = [
    # 课程元信息
    r'课程目标', r'适用人群', r'学习人群', r'目标人群', r'适合人群',
    r'学习方法', r'学习技巧', r'记忆方法', r'学习建议',
    r'课程大纲', r'章节概览', r'章节安排', r'课程安排',
    r'学前准备', r'课程背景', r'课程介绍', r'视频介绍',
    r'讲师', r'主讲', r'导师', r'老师介绍',
    # 教学计划
    r'教学进度', r'课时分配', r'学习安排', r'教学计划',
    r'考核方式', r'评分标准', r'作业要求',
    # 考试/等级
    r'考试要求', r'备考', r'英语四级', r'六级考试', r'考研', r'雅思', r'托福',
    r'等级考试', r'词汇量',
    # 鼓励/励志
    r'坚持', r'鼓励', r'加油', r'心态', r'励志', r'情绪', r'建议',
    r'最近学习', r'进步',
    # 元信息/列表
    r'共\d+个', r'第\d+-\d+个', r'将介绍', r'接下来学习', r'本节目标',
    r'本节开始', r'章节内容',
    # 课程推广
    r'收藏', r'点赞', r'关注', r'转发', r'投币', r'三连',
    r'抽奖', r'福利', r'优惠',
]

def _is_forbidden(text: str) -> bool:
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _mock_knowledge_extraction(text: str = "") -> List[Dict[str, Any]]:
    """模拟知识点提取结果（降级用），仅当输入包含学科关键词时生成，否则返回空列表"""
    if _is_forbidden(text):
        logger.info("模拟提取: 输入含禁提内容，返回空列表")
        return []

    keywords = _extract_keywords_from_text(text) if text else []
    if not keywords:
        return []

    main_kw = keywords[0]
    sub_kw = keywords[1] if len(keywords) > 1 else "原理"
    return [
        {
            "title": main_kw,
            "content": f"{main_kw}是{sub_kw}领域的核心概念，其基本原理是通过特定机制实现功能，理解它需要掌握定义和典型应用场景。",
            "difficulty": 0.4,
            "tags": [sub_kw, main_kw],
        }
    ]


def generate_fact_card(item) -> Dict[str, str]:
    """
    生成事实知识点的复习卡片。

    Args:
        item: KnowledgeItem对象

    Returns:
        卡片字典，包含title, content, hint, example, reference_answer
        - title: 知识点标题
        - content: 卡片正面核心内容（简洁，50-80字）
        - hint: 提示问题（帮助回忆）
        - example: 简短示例或关键词
        - reference_answer: 参考答案（与卡片互补：重新表述+示例+记忆技巧，100-200字）
    """
    title = getattr(item, 'title', '')
    original_content = getattr(item, 'content', '')
    tags = getattr(item, 'tags', []) or []
    domain = getattr(item, 'domain', '') or ''

    if USE_FALLBACK:
        tags_str = '、'.join(tags) if tags else '相关知识'
        return {
            "title": title,
            "content": original_content[:80] if original_content else title,
            "hint": f"你能用自己的话重新解释「{title}」吗？换个说法试试？",
            "example": f"在{domain or '实际'}场景中的{title}实例",
            "reference_answer": (
                f"换个角度理解：{original_content[:60] if original_content else title}的核心在于它的本质特性和应用场景。"
                f"例如，在{domain or '实际'}场景中，可以通过一个简单例子来验证它的作用。"
                f"记忆技巧：把{title}想象成一个{tags_str}中的角色，理解它与其他概念的互动关系。"
            )
        }

    prompt = f"""请为以下知识点生成一张复习卡片的参考答案。

知识点标题：{title}
知识点内容（卡片正面）: {original_content[:200]}
所属领域：{domain or '通用'}
标签：{', '.join(tags) if tags else '通用'}

请输出JSON对象，包含：
- reference_answer: 参考答案（100-200字），必须与卡片正面互补，包含以下三部分：
  **① 换个角度解释**：用不同的措辞重新表述核心定义，不是简单复制原内容
  **② 具体示例**：给一个简短的代码片段、公式代入或真实场景例子（如果涉及编程/数学/工程，必须给出代码或公式示例）
  **③ 记忆技巧/易错提醒**：一条助记方法或易混淆点的说明（至少一条）

要求：
- reference_answer必须与卡片正面的内容形成互补，不要重复相同的句子
- 如果涉及代码，给出具体代码示例；如果涉及公式，给出代入数值的计算过程
- 语言自然，像老师在给你讲解

只输出JSON，不要有其他文字。"""

    try:
        response = _call_deepseek(
            prompt,
            system_prompt="你是一个教育专家，擅长从不同角度解释知识，给出互补的参考答案。",
            temperature=0.4,
            json_mode=True
        )
        cleaned = response.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned)
        result.setdefault("title", title)
        result.setdefault("content", original_content[:80] if original_content else title)
        result.setdefault("hint", f"试试用自己的话解释「{title}」？")
        result.setdefault("example", f"{domain or '通用'}场景示例")
        return result
    except Exception as e:
        logger.error(f"复习卡片生成失败: {e}")
        return {
            "title": title,
            "content": original_content[:80] if original_content else title,
            "hint": f"试试用自己的话解释「{title}」？",
            "example": f"{domain or '通用'}场景中的{title}实例",
            "reference_answer": (
                f"换个角度理解：{original_content[:80] if original_content else title}的核心本质可以通过一个具体例子来理解。"
                f"在实际应用中，注意区分{title}与相关概念的边界条件。"
                f"记忆技巧：尝试用自己的话总结{title}的三要素——是什么、为什么、怎么用。"
            )
        }


def _detect_verify_type(item) -> str:
    """
    根据知识点深度、标签和内容自动检测最佳题型。
    仅返回前端已实现的题型集合: explain/calc/compare/debug/recite/apply/summarize

    Args:
        item: KnowledgeItem对象

    Returns:
        检测到的题型（必定属于已实现集合）
    """
    SUPPORTED = {'explain', 'calc', 'compare', 'debug', 'recite', 'apply', 'summarize'}

    def _clamp(vt):
        """将任意题型映射到已实现集合"""
        if vt in SUPPORTED:
            return vt
        mapping = {
            'causal': 'explain',
            'sensitivity': 'compare',
            'design': 'apply',
            'critique': 'explain',
            'synthesis': 'summarize',
            'evaluate': 'explain',
            'relation': 'compare',
            'variant': 'apply',
        }
        return mapping.get(vt, 'explain')

    title = getattr(item, 'title', '').lower()
    content = getattr(item, 'content', '').lower()
    tags = getattr(item, 'tags', []) or []
    domain = getattr(item, 'domain', '') or ''
    depth = getattr(item, 'depth', 'basic') or 'basic'

    tags_str = ' '.join(tags).lower() + ' ' + domain.lower()

    humanities_keywords = ['文学', '历史', '哲学', '艺术', '社会', '文化', '语言',
                           '政治', '法律', '教育', '宗教', '音乐', '美术']
    is_humanities = any(kw in tags_str for kw in humanities_keywords)

    has_formula = '$$' in content or '$' in content or any(
        kw in content for kw in ['公式', '方程', '函数', '算法', '推导', '计算']
    )

    raw_type = 'explain'

    if not is_humanities:
        if any(kw in content for kw in ['错误', 'bug', '故障', '问题代码', '常见错误', '误解', '陷阱']):
            raw_type = 'debug'
            return _clamp(raw_type)

    if depth == 'advanced':
        if is_humanities:
            raw_type = 'explain'
        elif any(kw in content for kw in ['结合', '综合', '融合', '交叉']):
            raw_type = 'summarize'
        elif has_formula:
            raw_type = 'calc'
        else:
            raw_type = 'summarize'
        return _clamp(raw_type)

    elif depth == 'intermediate':
        if is_humanities:
            raw_type = 'compare' if any(kw in content for kw in ['对比', '区别', '差异', 'vs']) else 'explain'
        elif any(kw in content for kw in ['对比', '区别', '差异', 'vs']):
            raw_type = 'compare'
        elif any(kw in content for kw in ['应用', '实现', '场景', '实践']):
            raw_type = 'apply'
        elif has_formula:
            raw_type = 'calc'
        else:
            raw_type = 'explain'
        return _clamp(raw_type)

    compare_keywords = ['对比', '区别', '差异', 'vs', '与…不同', '异同', '比较', '差异分析']
    for keyword in compare_keywords:
        if keyword in title or keyword in content or keyword in tags_str:
            return 'compare'

    apply_keywords = ['应用', '实现', '使用', '实践', '场景', '如何应用', '实际应用', '实战']
    for keyword in apply_keywords:
        if keyword in title or keyword in content or keyword in tags_str:
            return 'apply'

    debug_keywords = ['错误', '缺陷', 'bug', '常见错误', '修复', '调试', '问题', '修复方法']
    for keyword in debug_keywords:
        if keyword in title or keyword in content or keyword in tags_str:
            return 'debug'

    calc_keywords = ['计算', '推导', '证明', '求解', '公式', '算法', '优化', '收敛']
    for keyword in calc_keywords:
        if keyword in title or keyword in content or keyword in tags_str:
            return 'calc'

    if not is_humanities:
        if any(tag in tags_str for tag in ['编程', '代码', '算法', '软件开发']):
            return 'debug'
        if any(tag in tags_str for tag in ['数学', '计算', '公式', '推导']):
            return 'calc'
        if any(tag in tags_str for tag in ['物理', '化学', '工程']):
            return 'apply'

    if depth == 'basic':
        return 'summarize'

    return 'explain'


def _get_subject_preferred_types(subject: str) -> str:
    """
    根据学科获取优先的题型。
    
    Args:
        subject: 学科名称
    
    Returns:
        优先的题型
    """
    subject_preferences = {
        "数学": "calc",
        "编程": "debug",
        "物理": "apply",
        "化学": "apply",
        "生物": "explain",
        "历史": "explain",
        "文学": "explain",
        "其他": "explain"
    }
    return subject_preferences.get(subject, "explain")


def _fallback_question(item, verify_type: str) -> Dict[str, Any]:
    """
    从预置模板中生成题目。
    
    Args:
        item: KnowledgeItem对象
        verify_type: 验证类型

    Returns:
        题目字典
    """
    title = getattr(item, 'title', '')
    content = getattr(item, 'content', '') or ''
    domain = getattr(item, 'domain', '通用') or '通用'

    has_formula = '$$' in content or '$' in content or '=' in content

    if has_formula:
        calc_template = f'请写出「{title}」的核心公式，并解释公式中每个符号的含义。'
    else:
        calc_template = f'请详细解释「{title}」的核心原理，并给出一个具体应用例子。'

    if has_formula:
        causal_template = f'请阐述「{title}」从初始条件到最终结果的完整逻辑链条，并解释每一步的依据。'
        sensitivity_template = f'在「{title}」中，如果改变某个关键参数，结果会如何变化？请定性分析并解释原因。'
    else:
        causal_template = f'请分析「{title}」的因果关系链条，说明各因素之间如何相互影响。'
        sensitivity_template = f'请分析「{title}」中关键因素的变化对整体结果的影响。'

    type_specific_templates = {
        'compare': f'请比较「{title}」与相关概念的异同，并说明各自适用场景。',
        'apply': f'请设计一个使用「{title}」解决实际问题的具体方案，并说明实施步骤。',
        'debug': f'以下是关于「{title}」的一段论述，请指出其中的错误并说明如何修正。',
        'relation': f'请描述「{title}」与其他相关知识点的依赖关系和影响机制。',
        'explain': f'请详细解释「{title}」的定义和核心原理，并给出一个具体例子。',
        'recite': f'请复述「{title}」的核心定义和关键要点。',
        'variant': f'请举例说明「{title}」在日常生活或工作中的实际体现。',
        'calc': calc_template,
        'critique': f'请批判性分析「{title}」的理论假设、局限性及适用边界条件。',
        'synthesis': f'请将「{title}」与其他相关概念结合，提出一个综合性的解决方案或创新思路。',
        'evaluate': f'请评估以下关于「{title}」的论述："{content[:80]}..." 这一说法是否可靠？请说明理由。',
        'summarize': f'请用简洁的语言总结「{title}」的核心要点，不超过3句话。',
        'causal': causal_template,
        'sensitivity': sensitivity_template,
        'design': f'请基于「{title}」设计一个系统或方案，说明关键设计决策和实施步骤。',
    }

    if verify_type in type_specific_templates:
        question_text = type_specific_templates[verify_type]
    else:
        if has_formula:
            question_text = f'请解释「{title}」的核心公式或原理，并举例说明其应用。'
        else:
            question_text = f'请详细解释「{title}」的定义并举例说明。'

    return {
        'question_text': question_text,
        'verify_type': verify_type
    }


def generate_concept_question(item, verify_type: str = "auto", difficulty_offset: float = 0.0) -> Dict[str, Any]:
    """
    生成概念验证题目，支持智能题型选择和领域感知。
    """
    title = getattr(item, 'title', '')
    logger.info("[DEBUG] generate_concept_question for '%s', verify_type=%s", title, verify_type)
    print(f"[DIAG] generate_concept_question for '{title}', verify_type={verify_type}")
    content = getattr(item, 'content', '')
    tags = getattr(item, 'tags', []) or []
    domain = getattr(item, 'domain', '通用领域')
    depth = getattr(item, 'depth', 'basic') or 'basic'

    if verify_type == "auto":
        verify_type = _detect_verify_type(item)

    if USE_FALLBACK:
        return _fallback_question(item, verify_type)

    tags_str = '、'.join(tags) if tags else '通用'
    domain_style = f"（{domain}领域风格）"

    difficulty_offset = max(-0.2, min(0.2, difficulty_offset))
    difficulty_hints = {
        -0.2: "请出一道偏简单的题目，侧重基础概念理解。",
        0.0: "",
        0.2: "请出一道偏难的题目，要求更深入的分析和推理。"
    }
    if -0.2 < difficulty_offset < 0.0:
        difficulty_hint = "请适当降低题目难度，侧重基本概念。"
    elif 0.0 < difficulty_offset < 0.2:
        difficulty_hint = "请适当提高题目难度，要求更深入的分析。"
    else:
        difficulty_hint = difficulty_hints.get(round(difficulty_offset, 1), "")

    type_descriptions = {
        'compare': '对比题：要求用户明确阐述两个或多个概念之间的区别与联系',
        'apply': '应用题：要求用户运用概念解决实际问题或给出实现方案',
        'debug': '错误定位题：提供一个包含常见错误的陈述或代码片段，让用户找出并纠正错误',
        'relation': '关系题：要求描述概念之间的依赖关系或因果关系',
        'explain': '解释题：要求详细解释概念并举例说明',
        'recite': '复述题：要求详细解释概念定义和核心要点',
        'calc': '计算题：要求推导或计算相关问题',
        'summarize': '总结题：要求用户对复杂论述进行精炼总结，练习提炼能力',
    }

    prompt_examples = {
        'compare': '题目示例格式："请比较变分自编码器与GAN的异同，并说明各自适用场景。"',
        'apply': '题目示例格式："请设计一个使用有限元分析解决结构力学问题的方案。"',
        'debug': '题目示例格式："以下关于感知机的说法中存在错误：\u2018感知机可以解决异或分类问题，因为它是非线性分类器。\u2019请找出错误并纠正。"',
        'relation': '题目示例格式："请描述制度与交易成本之间的关系。"',
        'explain': '题目示例格式："请解释什么是蒙特卡洛方法，并说明其主要应用场景。"',
        'recite': '题目示例格式："请详细解释卷积神经网络的结构及其各层作用。"',
        'calc': '题目示例格式："请计算梯度下降算法在给定学习率下的收敛速度。"',
        'summarize': '题目示例格式："请用不超过100字总结以下关于制度经济学的核心观点：[论述内容]"',
    }

    depth_guidance = {
        'basic': '题目应侧重基础概念的理解和记忆，难度适中。',
        'intermediate': '题目应侧重原理理解和应用分析，可涉及实际场景。',
        'advanced': '题目应侧重深度分析、批判性思考或创新综合，具有挑战性。'
    }

    prompt = f"""请基于以下知识点内容生成一道{type_descriptions.get(verify_type, '验证')}题。

领域标签：{tags_str}
{domain_style}
知识深度：{depth} - {depth_guidance.get(depth, '')}
{difficulty_hint}

知识点：
标题：{title}
内容：{content}

{prompt_examples.get(verify_type, '')}

核心规则——题目必须与知识点内容的实际深度严格匹配：

**判断content中是否包含数学公式或推导步骤：**
- 如果content中包含LaTeX公式（如$...$或$$...$$）或明确的数学表达式，则：
  * 可以要求"写出公式"或"解释公式中每个符号的含义"
  * 可以要求代入具体数值进行计算
  * 可以要求推导公式（前提是content中已有推导步骤）
  * 例：对"感知机"可出题"请写出感知机的决策函数公式并解释w、x、b的含义"

- 如果content中没有公式（如历史事件、文学概念、社会现象等），则：
  * 题目应聚焦于概念应用、场景判断或举例说明
  * 绝对不要要求推导公式或进行数学计算
  * 例：对"制度经济学"可出题"请举例说明路径依赖如何导致低效制度长期存在"

**题型特定要求：**
- debug（错误定位）：提供一个包含常见错误的陈述或代码片段，让用户找出并纠正
- compare（对比题）：要求用户明确阐述两个或多个概念之间的区别与联系
- apply（应用题）：要求用户运用概念解决实际问题或给出实现方案
- calc（计算题）：要求推导或计算相关问题
- summarize（总结题）：要求用户对复杂论述进行精炼总结

**难度匹配原则：**
- content包含丰富的推导细节 → 可出推导题或计算题
- content仅包含定义和例子 → 出解释题或应用题
- 题目考察范围不能超出content已涵盖的内容

要求：
- 题目应具体、有针对性，结合领域特点
- 避免空洞的"请解释"，要多联系实际应用场景
- 根据{depth}深度调整题目难度
- 只输出题目文本，不要有任何额外解释或说明。"""

    try:
        response = _call_deepseek(prompt, system_prompt=f"你是一个专业的教育出题专家，擅长{domain}领域的题目设计。", temperature=0.5)

        if response and response.strip():
            return {
                'question_text': response.strip(),
                'verify_type': verify_type
            }
        else:
            logger.warning("DeepSeek API 返回空内容，使用fallback模板")
            return _fallback_question(item, verify_type)

    except Exception as e:
        logger.error(f"题目生成失败: {e}")
        return _fallback_question(item, verify_type)


def ai_evaluate_concept_answer(item, verify_type: str, answer: str) -> Dict[str, Any]:
    """
    评估用户对概念验证题的回答，返回结构化反馈：正确点、遗漏点、错误点、正确推导等。

    Args:
        item: KnowledgeItem对象
        verify_type: 验证类型
        answer: 用户回答

    Returns:
        {"score": float, "feedback": {"correct_parts": [...], "missing_parts": [...], "mistakes": [...], "correct_derivation": "...", "reference_answer": "...", "further_study": [...]}}
    """
    if USE_FALLBACK:
        return _mock_feedback_with_keywords(answer, item)

    title = getattr(item, 'title', '')
    content = getattr(item, 'content', '')
    formula = getattr(item, 'formula', '') or ''
    derivation_steps = getattr(item, 'derivation_steps', []) or []
    common_mistakes = getattr(item, 'common_mistakes', []) or []

    derivation_hint = ""
    if derivation_steps:
        derivation_hint = f"\n该知识点的正确推导步骤为：\n" + "\n".join(derivation_steps)

    formula_hint = ""
    if formula:
        formula_hint = f"\n该知识点的核心公式为：{formula}"

    prompt = f"""你是一位严谨的理科导师。请评估用户对以下概念的回答，并输出详细的结构化反馈。

概念：{title}
内容：{content}{formula_hint}{derivation_hint}

用户回答：{answer}

输出JSON格式，包含：
- score: 0-1之间的浮点数（评分标准见下）
- correct_parts: 字符串数组，用户回答中正确提到的内容片段（如["正确给出了公式", "举了合理的例子"]，若无则["没有明显正确的内容"]）
- missing_parts: 字符串数组，用户遗漏的关键点（如["未提供公式", "没有解释参数含义", "缺少实际应用场景"]，至少列出1个）
- mistakes: 字符串数组，用户回答中的具体错误（如["错误地将激活函数写作sigmoid", "混淆了权重和偏置的定义"]，若无则空数组[]）
- correct_derivation: 正确的推导过程或详细解答（一段文字，若为非推导类题目可写关键思路）
- reference_answer: 一份完整的参考答案（涵盖所有关键点，3-5句话）
- further_study: 推荐学习内容列表（1-3项）
- error_type: 错误类型标签，从以下选择最匹配的一个："概念混淆"、"公式错误"、"计算失误"、"遗漏关键点"、"理解偏差"、"表达不清"，若无明显错误则为null

评分标准（0-1）：
- 0.9-1.0：准确、完整、逻辑清晰，无重要遗漏，公式推导正确
- 0.7-0.89：正确但略有遗漏或不够深入，核心内容正确
- 0.5-0.69：部分正确，关键点缺失或轻微错误
- 0.3-0.49：大部分错误或严重遗漏
- 0.0-0.29：完全错误或无关

要求：
- correct_parts必须具体，引用用户回答中的实际内容，不要泛泛说"回答了部分内容"
- missing_parts必须指出具体的遗漏点，如"未写出具体公式"而不是"回答不够详细"
- mistakes必须定位到具体错误，如"你说X=Y是错的，正确的是X=Z"
- correct_derivation应包含完整的推导逻辑或解题思路，不是一两句话
- 不要输出任何额外文字，只输出JSON。"""

    try:
        response = _call_deepseek(prompt, system_prompt="你是一位专业的教育评估专家，擅长细致入微地批改学生答案。", temperature=0.3, json_mode=True)
        cleaned = response.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned)

        feedback = result.get('feedback', {})
        if not feedback:
            feedback = result

        return {
            'score': max(0.0, min(1.0, float(result.get('score', 0.5)))),
            'feedback': {
                'correct_parts': _ensure_str_list(feedback.get('correct_parts', []), ["回答已提交"]),
                'missing_parts': _ensure_str_list(feedback.get('missing_parts', []), ["部分关键内容未覆盖"]),
                'mistakes': _ensure_str_list(feedback.get('mistakes', []), []),
                'correct_derivation': str(feedback.get('correct_derivation', '暂无推导过程')),
                'reference_answer': str(feedback.get('reference_answer', '')),
                'further_study': [str(s) for s in feedback.get('further_study', [])][:3],
                'summary': str(feedback.get('reference_answer', '回答评估完成。')),
                'error_type': str(feedback.get('error_type', '')) if feedback.get('error_type') else None,
            }
        }
    except Exception as e:
        logger.error(f"答案评估失败: {e}")
        return _mock_feedback_with_keywords(answer, item)


def _ensure_str_list(value, default):
    """确保值是字符串数组"""
    if isinstance(value, list) and len(value) > 0:
        return [str(v) for v in value][:10]
    return default


def _mock_feedback_with_keywords(answer: str, item=None) -> Dict[str, Any]:
    """基于用户答案长度和关键词的模拟反馈（新格式）"""
    title = getattr(item, 'title', '知识点') if item else '知识点'
    content = getattr(item, 'content', '') if item else ''
    formula = getattr(item, 'formula', '') if item else ''

    answer_length = len(answer.strip())

    if answer_length < 20:
        score = 0.3
        correct_parts = []
        missing_parts = ["未提供完整定义", "缺少具体例子", "没有写出公式或原理"]
        mistakes = ["回答过于简略，无法验证理解程度"]
        correct_derivation = f"{title}是经典力学的基础定律之一。任何物体都具有惯性，在没有外力作用时保持匀速直线运动或静止。" + (f" 核心公式：{formula}" if formula else "")
        reference_answer = f"{title}：{content[:120]}"
        further_study = ["查看教材相关章节", f"{title}入门教程"]
    elif answer_length < 50:
        score = 0.5
        correct_parts = ["给出了基本框架"]
        missing_parts = ["缺少深入解释", "没有举具体例子"]
        mistakes = []
        correct_derivation = f"根据{title}的核心原理，完整解答应包括：1) 明确定义；2) 写出公式；3) 代入数值计算；4) 说明注意事项。" + (f" 关键公式：{formula}" if formula else "")
        reference_answer = f"{title}的核心定义是理解这个概念的关键。" + (f" 核心公式：{formula}" if formula else "")
        further_study = ["相关例题练习", f"{title}应用案例"]
    elif "因为" in answer or "所以" in answer:
        score = 0.7
        correct_parts = ["给出了因果分析", "回答了核心问题"]
        missing_parts = ["可以更精确地表述公式"]
        mistakes = []
        correct_derivation = "解题思路：第一步明确已知条件，第二步应用核心公式，第三步代入计算，第四步得出结果并验证。"
        reference_answer = f"{title}是一个重要概念，理解其核心机制很关键。" + (f" 关键公式：{formula}" if formula else "")
        further_study = [f"{title}进阶内容", "相关理论深入学习"]
    elif "例如" in answer or "比如" in answer:
        score = 0.75
        correct_parts = ["举了具体例子", "回答结构清晰"]
        missing_parts = ["可以补充公式推导"]
        mistakes = []
        correct_derivation = "推导过程如下：从基本定义出发 → 展开公式 → 代入条件 → 得出最终表达式。"
        reference_answer = f"{title}的核心原理需要结合理论和实践来理解。" + (f" 关键公式：{formula}" if formula else "")
        further_study = ["理论基础学习", f"{title}案例分析"]
    else:
        score = 0.6
        correct_parts = ["回答内容基本相关"]
        missing_parts = ["缺少公式表达", "没有明确的结构化回答"]
        mistakes = []
        correct_derivation = f"针对{title}的正确推导思路是：首先理解基本概念，然后分析其数学表达，接着考虑边界条件，最后总结关键结论。"
        reference_answer = f"{title}包含以下核心要点：1) 基本定义；2) 核心原理；3) 实际应用。"
        further_study = [f"{title}学习指南", "相关知识点梳理"]

    return {
        "score": score,
        "feedback": {
            "correct_parts": correct_parts,
            "missing_parts": missing_parts,
            "mistakes": mistakes,
            "correct_derivation": correct_derivation,
            "reference_answer": reference_answer,
            "further_study": further_study,
            "summary": reference_answer,
            "error_type": "遗漏关键点" if answer_length < 50 else ("理解偏差" if score < 0.6 else None),
        }
    }


def auto_classify(content: str) -> str:
    """
    自动分类知识点类型。
    
    Args:
        content: 知识点内容
    
    Returns:
        "fact" 或 "concept"
    """
    if USE_FALLBACK:
        if len(content) < 50 or ("是" in content and "定义" in content):
            return "fact"
        return "concept"
    
    prompt = f"""请判断以下内容属于事实(fact)还是概念(concept)：

内容：{content}

规则：
- fact（事实）：客观陈述、定义、数据、名词解释
- concept（概念）：需要理解、解释、应用的理论、原理、方法

只输出"fact"或"concept"，不要有其他文字。"""
    
    try:
        response = _call_deepseek(prompt, system_prompt="你是一个分类专家。", temperature=0.0)
        result = response.strip().lower()
        if result in ["fact", "concept"]:
            return result
        return "concept"
    except Exception as e:
        logger.error(f"分类失败: {e}")
        return "concept"


def analyze_prerequisites(content: str) -> List[int]:
    """
    分析知识点的前置知识。初赛返回空列表。
    
    Args:
        content: 知识点内容
    
    Returns:
        前置知识ID列表（初赛返回空列表）
    """
    return []


def evaluate_coding_code(problem: str, code: str) -> Dict[str, Any]:
    """
    评估编程代码。
    
    Args:
        problem: 编程题目描述
        code: 用户提交的代码
    
    Returns:
        评估结果
    """
    if USE_FALLBACK:
        return {
            'score': 0.75,
            'feedback': '代码逻辑基本正确，建议添加更多测试用例验证边界条件。',
            'suggestion': '考虑增加输入参数校验和异常处理。',
            'growth_increment': 25
        }
    
    prompt = f"""请评估以下代码是否正确解决了给定的编程问题。

问题描述：{problem}

用户代码：
{code}

请输出JSON对象，包含：
- score: 0-1的分数
- feedback: 代码评估反馈
- suggestion: 改进建议
- growth_increment: 成长值增量（0-50）

只输出JSON，不要有其他文字。"""
    
    try:
        response = _call_deepseek(prompt, system_prompt="你是一个编程导师和代码评审专家。", temperature=0.3, json_mode=True)
        cleaned = response.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned)
        return {
            'score': max(0.0, min(1.0, float(result.get('score', 0.5)))),
            'feedback': str(result.get('feedback', '')),
            'suggestion': str(result.get('suggestion', '')),
            'growth_increment': max(0, min(50, int(result.get('growth_increment', 25))))
        }
    except Exception as e:
        logger.error(f"代码评估失败: {e}")
        return {
            'score': 0.6,
            'feedback': '代码评估失败，请重试。',
            'suggestion': '检查代码语法和逻辑。',
            'growth_increment': 15
        }


def generate_coding_question(item) -> Dict[str, Any]:
    """
    生成编程题目。
    
    Args:
        item: KnowledgeItem对象
    
    Returns:
        编程题目字典
    """
    title = getattr(item, 'title', '')
    content = getattr(item, 'content', '')
    
    if USE_FALLBACK:
        return {
            'title': title,
            'description': f'请实现一个与"{title}"相关的函数。',
            'examples': [
                {'input': '示例输入', 'output': '示例输出'}
            ]
        }
    
    prompt = f"""请根据以下知识点生成一道编程题目。

知识点：{title}
内容：{content}

请输出JSON对象，包含：
- title: 题目标题
- description: 题目描述
- examples: 示例列表，每个示例包含input和output

只输出JSON，不要有其他文字。"""
    
    try:
        response = _call_deepseek(prompt, system_prompt="你是一个编程题生成专家。", temperature=0.5, json_mode=True)
        cleaned = response.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned)
    except Exception as e:
        logger.error(f"编程题目生成失败: {e}")
        return {
            'title': title,
            'description': f'请实现一个与"{title}"相关的功能。',
            'examples': [{'input': '', 'output': ''}]
        }


def generate_assistant_message(avg_score: float, new_count: int) -> str:
    """
    根据用户学习数据生成鼓励或建议消息。
    
    Args:
        avg_score: 最近3次答题的平均得分（0-1）
        new_count: 新种植的知识点数量
    
    Returns:
        助教版消息
    """
    if USE_FALLBACK:
        return random.choice(DEFAULT_MESSAGES)
    
    prompt = f"""你是一个温暖、有趣的学习助教小狐狸🦊。根据以下用户学习数据，生成一句20字以内的鼓励或建议消息。

用户数据：
- 最近3次平均得分: {avg_score:.0%}
- 新学了 {new_count} 个知识点

要求：
- 消息要像朋友一样自然亲切
- 使用表情符号增加亲和力
- 长度不超过20字
- 可以是鼓励或建议
- 语气轻松有趣

只输出消息内容，不要有其他文字。"""
    
    try:
        response = _call_deepseek(prompt, system_prompt="你是一个可爱的小狐狸助教，说话温暖有趣。", temperature=0.8)
        result = response.strip()
        if result and len(result) <= 30:
            return result
        return random.choice(DEFAULT_MESSAGES)
    except Exception as e:
        logger.error(f"生成助教消息失败: {e}")
        return random.choice(DEFAULT_MESSAGES)


def generate_topic_summary(tags: List[str], knowledge_items: List[Dict[str, Any]]) -> str:
    """
    根据标签相关的知识点生成专题总结。
    
    Args:
        tags: 专题标签列表
        knowledge_items: 相关知识点列表
    
    Returns:
        Markdown格式的总结报告
    """
    if USE_FALLBACK:
        return _mock_topic_summary(tags)
    
    tags_str = "、".join(tags) if tags else "相关主题"
    
    items_text = "\n\n".join([
        f"## {item.get('title', '')}\n{item.get('content', '')}"
        for item in knowledge_items
    ])
    
    prompt = f"""你是一位学科总结专家。请根据以下知识点生成一份结构化的专题总结报告。

专题标签：{tags_str}
相关知识点：
{items_text}

请生成Markdown格式，包含：
# {tags_str}专题总结

## 1. 核心概念定义
（对相关概念的核心定义）

## 2. 概念之间的关联图谱（文字描述）
（说明各个概念之间的关系、依赖、层级等）

## 3. 常见应用场景
（列出2-3个典型应用场景）

## 4. 值得进一步研究的问题
（2-3个进阶思考问题）

要求：
- 内容精炼，重点突出
- 逻辑清晰，层次分明
- 用词专业，表述准确
- 字数控制在500-1000字之间"""
    
    try:
        response = _call_deepseek(prompt, system_prompt="你是一位专业的学科总结专家，擅长知识结构化梳理。", temperature=0.6)
        return response.strip()
    except Exception as e:
        logger.error(f"生成专题总结失败: {e}")
        return _mock_topic_summary(tags)


def _mock_topic_summary(tags: List[str]) -> str:
    """模拟专题总结"""
    tags_str = "、".join(tags) if tags else "相关主题"
    return f"""# {tags_str}专题总结

## 1. 核心概念定义
本专题涵盖了核心概念，涉及到相关领域的重要知识点。主要概念包括基础定义和核心原理。

## 2. 概念之间的关联图谱（文字描述）
各个概念之间存在层级关系，从基础到高级逐步递进。基础概念是高级概念的基础，高级概念是基础概念的延伸和应用。

## 3. 常见应用场景
- 场景一：基础应用场景描述
- 场景二：进阶应用场景描述
- 场景三：综合应用场景描述

## 4. 值得进一步研究的问题
1. 如何更好地理解和掌握相关概念
2. 如何在实际项目中有效应用
3. 相关领域的最新研究进展和未来趋势"""


def evaluate_and_answer_question(question: str, related_knowledge_items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    评价用户提问的质量，并给出回答或引导。
    
    Args:
        question: 用户提问内容
        related_knowledge_items: 相关知识点列表（可选）
    
    Returns:
        包含质量评分、反馈和答案的字典
    """
    if USE_FALLBACK:
        return _mock_question_evaluation(question)
    
    related_text = ""
    if related_knowledge_items and len(related_knowledge_items) > 0:
        related_text = "\n\n相关知识点背景：\n" + "\n".join([
            f"- {item.get('title', '')}: {item.get('content', '')[:100]}..."
            for item in related_knowledge_items[:3]
        ])
    
    prompt = f"""你是一位提问能力训练导师。请先评价用户提问的质量，然后给出回答或引导进一步思考。

用户提问：{question}{related_text}

请输出JSON格式，包含：
- quality_score: 0-1的质量评分
- feedback: 对提问质量的反馈（评估清晰度、深度等）
- answer: 对问题的回答或引导
- suggestion: 如何更好提问的建议

要求：
- quality_score: 0.3-0.5=一般，0.5-0.7=良好，0.7-1.0=优秀
- feedback: 评价清晰度、深度、是否具体等
- answer: 专业回答，若问题不清晰则引导澄清
- suggestion: 1-2个具体改进建议

只输出JSON，不要有其他文字。"""
    
    try:
        response = _call_deepseek(prompt, system_prompt="你是一位专业的提问能力训练导师。", temperature=0.5, json_mode=True)
        cleaned = response.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned)
        
        return {
            'quality_score': max(0.0, min(1.0, float(result.get('quality_score', 0.5)))),
            'feedback': str(result.get('feedback', '')),
            'answer': str(result.get('answer', '')),
            'suggestion': str(result.get('suggestion', ''))
        }
    except Exception as e:
        logger.error(f"提问评估失败: {e}")
        return _mock_question_evaluation(question)


def _mock_question_evaluation(question: str) -> Dict[str, Any]:
    """模拟提问评估和回答"""
    q_len = len(question.strip())
    
    if q_len < 15:
        return {
            'quality_score': 0.4,
            'feedback': '问题过于简短，不够清晰具体，建议补充更多细节。',
            'answer': '这个问题有点简单，建议你把问题补充得更具体一些，我会更好地帮助你！',
            'suggestion': '1. 增加问题的背景信息 2. 说明你的具体困惑点'
        }
    elif "如何" in question or "为什么" in question:
        return {
            'quality_score': 0.7,
            'feedback': '问题提得不错！聚焦明确，是个很好的思考问题。',
            'answer': '这是一个很好的问题！这个问题涉及到重要的概念和原理，需要从多个角度来分析。',
            'suggestion': '继续保持这种深度思考的提问方式！'
        }
    elif "区别" in question or "比较" in question:
        return {
            'quality_score': 0.8,
            'feedback': '提问有深度！比较性问题体现了你的思考能力！',
            'answer': '很好的比较问题！这涉及概念对比很有价值，让我们从不同维度来分析。',
            'suggestion': '很棒的提问！可以尝试进一步深入探讨。'
        }
    else:
        return {
            'quality_score': 0.6,
            'feedback': '问题基本清晰，但可以更聚焦一些。',
            'answer': '让我们来一起探讨这个问题。这是个值得思考的话题。',
            'suggestion': '可以尝试问更具体的问题，比如问"如何..."或"为什么..."'
        }


def structure_video_content(full_text: str, video_title: str) -> Dict[str, Any]:
    """
    将视频字幕文本结构化为学习笔记。

    Args:
        full_text: 字幕全文（含时间戳）
        video_title: 视频标题

    Returns:
        包含 summary, knowledge_points, timestamp_index, qa_pairs 的字典
    """
    if len(full_text) > MAX_PROMPT_LEN:
        if ENABLE_SUMMARY_COMPRESS and len(full_text) > SUMMARY_THRESHOLD:
            compressed = summarize_long_text(full_text, target_length=800)
            if len(compressed) < len(full_text):
                full_text = compressed
                logger.info("视频字幕已摘要压缩: %d -> %d 字符", len(full_text), len(full_text))

        if len(full_text) > MAX_PROMPT_LEN:
            full_text = full_text[:MAX_PROMPT_LEN]

    prompt = f"""请分析以下视频字幕内容，生成结构化学习笔记。只提取真正的学科知识点，严禁提取课程元信息。

视频标题：{video_title}
字幕内容：
{full_text}

请输出JSON对象，包含以下字段：
- "summary": 核心摘要（200字以内，概括视频主要内容）
- "knowledge_points": 知识点列表，每个知识点包含：
  - "title": 知识点标题
  - "content": 核心内容描述
  - "type": "concept" 或 "fact"
  - "difficulty": 1-5的难度等级
  - "tags": 标签列表（如["深度学习","神经网络"]）
  - "domain": 所属领域（如"计算机科学"）
  - "timestamp": 在视频中出现的时间点（如"05:30"）
- "timestamp_index": 关键时间戳索引，格式为 [{{"time": "02:30", "topic": "主题"}}]
- "qa_pairs": 问答对列表，格式为 [{{"question": "问题", "answer": "简短答案"}}]

【严禁提取的内容类型（无条件过滤）】
以下内容属于"课程元信息"，不是学科知识，必须跳过：
- 课程结构描述：课程目标、适用人群、学习方法、课程大纲、章节安排、学前准备
- 教学计划/进度信息：教学进度、课时分配、学习安排、考核方式
- 过渡/引导语句："本视频会介绍"、"接下来我们将学习"、"前面我们讲了"
- 纯鼓励性/号召性语句："坚持学习"、"加油"、"每天进步"、"关注收藏"
- 列表索引/编号（无实际知识内容）："前缀第1-5个"、"共12个前缀"
- 考试/等级/证书相关信息：考研要求、四级词汇量、考试技巧、备考策略
- 讲师个人介绍、视频制作说明、背景故事（与学科无关的部分）

【知识点准入标准（必须同时满足）】
每个提取的知识点必须满足以下全部条件：
1. 可定义性：它能被一句话定义"XX是什么"
2. 可解释性：能用50-100字清晰解释其含义、原理或用法
3. 可应用性：可以用于解决实际问题或回答相关题目
4. 独立性：脱离原视频/课程上下文后仍可独立理解
5. 学科性：属于某个明确学科领域（语言、数学、编程、物理、历史、化学等）

【Few-shot 示例 —— 好的知识点 ✅】
- "词根 'ex-' 表示向外、出" ✅ (可定义、可解释、可应用)
- "梯度下降是一种通过迭代更新参数来最小化损失函数的优化算法" ✅
- "牛顿第一定律：物体在不受外力时保持静止或匀速直线运动" ✅

【Few-shot 示例 —— 不好的知识点 ❌ 必须跳过】
- "课程目标：掌握12大前缀" ❌ (课程元信息)
- "适用人群：英语学习者" ❌ (课程元信息)
- "学习方法：每天背诵5个词根" ❌ (学习建议)
- "本视频将介绍词根词缀法" ❌ (课程介绍)
- "前缀第1-5个：ex-, pre-, re-, un-, dis-" ❌ (纯列表无解释)

如果视频中确实没有可提取的学科知识（或只有课程元信息），knowledge_points 输出空数组 []

只输出JSON，不要有其他文字。"""

    try:
        response = _call_deepseek(
            prompt,
            system_prompt="你是教育内容分析专家，只提取可定义、可解释、可应用且独立于课程上下文的学科知识点（定义/公式/原理/代码/算法/事实）。严禁提取课程目标、适用人群、学习方法、课程大纲、章节安排、考试要求、鼓励语句、纯列表索引元信息等。若无可提取的学科知识则knowledge_points输出空数组。",
            temperature=0.3,
            json_mode=True,
        )
        cleaned = response.strip().replace("```json", "").replace("```", "")
        result = json.loads(cleaned)

        if "knowledge_points" not in result:
            result["knowledge_points"] = []
        if "timestamp_index" not in result:
            result["timestamp_index"] = []
        if "qa_pairs" not in result:
            result["qa_pairs"] = []
        if "summary" not in result:
            result["summary"] = ""

        filtered_kps = []
        for kp in result.get("knowledge_points", []):
            title = kp.get("title", "")
            content = kp.get("content", "")
            combined = title + content
            if _is_forbidden(combined):
                logger.info("视频知识点过滤(非学科): title=%s", title)
                continue
            filtered_kps.append(kp)
        result["knowledge_points"] = filtered_kps

        return result
    except Exception as e:
        logger.error("视频内容结构化失败: %s", e)
        return _mock_video_structure(video_title)


def _mock_video_structure(video_title: str = "") -> Dict[str, Any]:
    """模拟视频内容结构化结果（降级模式，根据标题动态生成）"""
    keywords = _extract_keywords_from_text(video_title, max_keywords=3) if video_title else ["知识点"]
    main_kw = keywords[0] if keywords else "知识点"
    sub_kw = keywords[1] if len(keywords) > 1 else "相关概念"
    return {
        "summary": f"本视频系统讲解了{main_kw}的基础概念和核心原理，涵盖定义、应用场景和常见问题。",
        "knowledge_points": [
            {
                "title": f"{main_kw}的核心定义",
                "content": f"{main_kw}是一个重要的概念，在{sub_kw}领域具有关键作用。核心定义：{main_kw}指的是在特定领域中具有基础性地位的理论或方法。",
                "type": "concept",
                "difficulty": 2,
                "tags": [main_kw, sub_kw],
                "domain": "通用",
                "timestamp": "02:30",
            },
            {
                "title": f"{main_kw}的应用场景",
                "content": f"{main_kw}在实际中有广泛的应用。典型应用包括在{sub_kw}领域中的实践，以及相关的计算和分析方法。",
                "type": "fact",
                "difficulty": 2,
                "tags": [main_kw, "应用"],
                "domain": "通用",
                "timestamp": "08:00",
            },
        ],
        "timestamp_index": [
            {"time": "00:00", "topic": f"{main_kw}介绍"},
            {"time": "02:30", "topic": f"{main_kw}定义"},
            {"time": "08:00", "topic": f"{main_kw}应用"},
        ],
        "qa_pairs": [
            {"question": f"什么是{main_kw}？", "answer": f"{main_kw}是在{sub_kw}领域中具有重要地位的概念。"},
        ],
    }