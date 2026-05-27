"""
本地自动摘要服务：提取式生成标题、标签、摘要。

无需外部 LLM API，纯本地规则 + TF-IDF 关键词提取。
"""

import re
import logging
from collections import Counter

logger = logging.getLogger(__name__)

# 常见中英文停用词
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "这个", "那个", "什么", "怎么", "如何", "可以", "还是", "只是", "但是",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "nor", "not", "so", "yet", "both", "either", "neither", "each", "every",
    "all", "any", "few", "more", "most", "other", "some", "such", "only",
    "own", "same", "than", "too", "very", "just", "because", "about",
}

# 技术关键词加权（这些词在 AI 对话中经常出现，应该高亮）
TECH_KEYWORDS = {
    "agent", "rag", "llm", "embedding", "vector", "database", "chromadb",
    "langchain", "prompt", "fine-tune", "token", "transformer", "gpu",
    "api", "微服务", "架构", "部署", "docker", "kubernetes", "react",
    "python", "fastapi", "sql", "神经网络", "模型", "训练", "推理",
    "memory", "检索", "搜索", "排序", "算法", "系统", "设计",
}


def generate_summary(messages: list[dict]) -> dict:
    """从消息列表中生成摘要信息。

    Args:
        messages: [{"role": "user/assistant", "content": "..."}, ...]

    Returns:
        {"title": str, "tags": str, "summary": str}
    """
    if not messages:
        return {"title": "", "tags": "", "summary": ""}

    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    assistant_messages = [m["content"] for m in messages if m["role"] == "assistant"]
    all_content = " ".join(m["content"] for m in messages)

    title = _extract_title(user_messages, assistant_messages)
    tags = _extract_tags(all_content)
    summary = _extract_summary(user_messages, assistant_messages)

    return {"title": title, "tags": tags, "summary": summary}


def _extract_title(user_messages: list[str], assistant_messages: list[str]) -> str:
    """从首条用户消息中提取标题。"""
    if user_messages:
        first = user_messages[0].strip()
        # 取第一个句子或前 50 个字符
        sentence = re.split(r'[。！？\n.!?]', first)[0].strip()
        if len(sentence) > 50:
            sentence = sentence[:50] + "..."
        return sentence
    if assistant_messages:
        first = assistant_messages[0].strip()
        sentence = re.split(r'[。！？\n.!?]', first)[0].strip()
        if len(sentence) > 50:
            sentence = sentence[:50] + "..."
        return sentence
    return "未命名对话"


def _extract_tags(text: str, top_n: int = 5) -> str:
    """使用 TF-IDF 风格的关键词提取。"""
    # 分词：中文按字符/词组，英文按空格
    words = _tokenize(text)

    # 过滤停用词和短词
    filtered = [w for w in words if w not in STOP_WORDS and len(w) >= 2]

    # 词频统计
    counter = Counter(filtered)

    # 技术关键词加权
    for kw in TECH_KEYWORDS:
        if kw.lower() in text.lower():
            counter[kw] = counter.get(kw, 0) + 5  # 加权

    # 取 top N
    top_tags = [word for word, _ in counter.most_common(top_n)]

    # 添加 # 前缀
    return ", ".join(f"#{tag}" for tag in top_tags)


def _extract_summary(user_messages: list[str], assistant_messages: list[str]) -> str:
    """提取对话摘要（首条用户消息 + 关键信息）。"""
    parts = []

    if user_messages:
        parts.append(f"用户提问：{user_messages[0][:200]}")

    if assistant_messages:
        # 取最后一条助手回复的前 300 字
        last = assistant_messages[-1]
        if len(last) > 300:
            last = last[:300] + "..."
        parts.append(f"AI 回答要点：{last}")

    return "\n".join(parts)


def _tokenize(text: str) -> list[str]:
    """简易中英文分词。

    中文：按常见分隔符切分 + 2-gram 字符级切分
    英文：按空格和标点切分
    """
    # 统一小写（英文）
    text_lower = text.lower()

    # 提取中文和英文词汇
    # 英文单词
    en_words = re.findall(r'[a-zA-Z][a-zA-Z0-9_+#-]{1,}', text_lower)

    # 中文词：去除英文和标点后的中文字符连续序列
    chinese_only = re.sub(r'[a-zA-Z0-9\s]+', ' ', text_lower)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', chinese_only)

    # 中文 2-gram（双字词组）更准确
    chinese_bigrams = []
    for i in range(len(chinese_chars) - 1):
        chinese_bigrams.append(chinese_chars[i] + chinese_chars[i + 1])

    # 中文单字（保留有意义的长词）
    chinese_long = re.findall(r'[\u4e00-\u9fff]{2,4}', text_lower)

    return en_words + chinese_bigrams + chinese_long
