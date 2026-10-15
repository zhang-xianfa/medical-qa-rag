
"""
# =============================================================================
# 医学知识库的"质检员"与"入库管家"
# 
# 这个文件负责在知识存入数据库之前，进行清洗、打分和去重。
# 确保AI检索到的每一条资料都是：格式完整、不重复、有权威度、有时效性。
# 
# 包含四个核心功能：
# 1. compute_content_hash：给内容生成唯一指纹（用于去重）
# 2. compute_freshness_score：根据出版年份计算时效分（越新分越高）
# 3. AUTHORITY_DEFAULTS：不同来源类型的默认权威分配置
# 4. load_from_dicts：批量入库主函数（校验+去重+自动打分）
# =============================================================================
"""

import hashlib


def compute_content_hash(content: str) -> str:
    """
    给知识内容生成SHA256指纹。
    作用：两段文字只要有一个标点不同，指纹就完全不同。
    用途：入库时靠它判断是不是重复内容，避免同一份指南被存多次。
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_freshness_score(publish_year: int, current_year: int = 2026) -> float:
    """
    计算知识的"新鲜度"得分（0~1之间）。

    打分规则：
    - 基础分：每年衰减0.1（10年前的知识基础分为0）
    - 惩罚项：超过5年的老知识，额外再打7折
    - 示例：2025年出版 → 0.9；2020年出版 → 0.4×0.7=0.28

    ⚠️ 医疗场景特别说明：
    老知识不一定没用（经典教材依然权威），所以这里只是"时效分"，
    最终排序会结合 authority_score 一起用，不会单纯因为旧就丢弃。
    """
    base_score = max(0.0, 1.0 - (current_year - publish_year) / 10.0)
    if (current_year - publish_year) > 5:
        base_score *= 0.7
    return round(base_score, 4)


# 不同来源类型的默认权威分（人工预设的先验知识）
# 临床指南 > 专家共识 > 教科书 > 综述 > 个案报道
AUTHORITY_DEFAULTS = {
    "guideline": 0.9,  # 临床指南：最高权威，AI应优先采信
    "consensus": 0.75,  # 专家共识：次高，多个专家达成一致的意见
    "textbook": 0.6,  # 教科书：基础知识可靠，但更新较慢
    "review": 0.5,  # 综述：总结性文章，参考价值中等
    "case_report": 0.2,  # 个案报道：仅个别案例，不能作为普遍依据
}


def validate_entry(entry: dict) -> bool:
    """
    校验知识条目是否合格。
    必须同时包含5个必填字段且不能为空，否则直接丢弃。
    防止残缺数据进入知识库，导致AI引用时出现空白或报错。
    """
    required = ["title", "source", "source_type", "publish_year", "content"]
    return all(k in entry and entry[k] for k in required)


def load_from_dicts(entries: list[dict]) -> list[dict]:
    """
    批量入库主函数：把原始知识列表处理成可入库的标准格式。

    处理流程（按顺序执行）：
    1. 校验：过滤掉字段不全的脏数据
    2. 去重：用内容指纹跳过已存在的重复条目
    3. 补全：自动计算并填充 content_hash、authority_score、freshness_score、tags

    Returns:
        list[dict]: 清洗完毕、可直接写入 VectorStore 的知识列表
    """
    loaded = []
    seen = set()  # 记录已处理的内容指纹，用于去重

    for entry in entries:
        # 第1步：校验不合格直接跳过
        if not validate_entry(entry):
            continue

        # 第2步：内容指纹去重
        content_hash = compute_content_hash(entry["content"])
        if content_hash in seen:
            continue
        seen.add(content_hash)

        # 第3步：补全所有衍生字段
        entry["content_hash"] = content_hash

        # 权威分：优先用数据自带的，没有则按来源类型取默认值
        entry["authority_score"] = entry.get(
            "authority_score",
            AUTHORITY_DEFAULTS.get(entry.get("source_type", ""), 0.5)
        )

        # 时效分：根据出版年份自动计算
        entry["freshness_score"] = compute_freshness_score(
            entry.get("publish_year", 2026)
        )

        # 标签：没有则初始化为空列表
        entry["tags"] = entry.get("tags", [])

        loaded.append(entry)

    return loaded