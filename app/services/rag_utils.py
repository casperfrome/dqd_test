"""Shared RAG utilities: token estimation, context truncation, MMR reranking, query expansion."""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Domain synonym pairs (Chinese ↔ English / code jargon) ──────────
_SYNONYM_PAIRS: list[tuple[str, str]] = [
    # Database domain
    ("用户", "user"),
    ("表", "table"),
    ("字段", "column"),
    ("索引", "index"),
    ("外键", "foreign_key"),
    ("数据库", "database"),
    ("查询", "query"),
    ("样例", "sample"),
    ("行", "row"),
    ("名称", "name"),
    ("类型", "type"),
    ("默认", "default"),
    ("约束", "constraint"),
    ("唯一", "unique"),
    ("主键", "primary_key"),
    ("自增", "increment"),
    ("注释", "comment"),
    ("状态", "status"),
    ("大小", "size"),
    ("路径", "path"),
    # Code domain
    ("登录", "login"),
    ("认证", "auth"),
    ("授权", "authorize"),
    ("令牌", "token"),
    ("密码", "password"),
    ("配置", "config"),
    ("路由", "router"),
    ("端点", "endpoint"),
    ("中间件", "middleware"),
    ("服务", "service"),
    ("仓库", "repository"),
    ("模式", "schema"),
    ("模型", "model"),
    ("组件", "component"),
    ("钩子", "hook"),
    ("状态", "state"),
    ("属性", "props"),
    ("接口", "interface"),
    ("函数", "function"),
    ("类", "class"),
    ("导入", "import"),
    ("错误", "error"),
    ("日志", "log"),
    ("测试", "test"),
    ("流", "stream"),
    ("会话", "session"),
    ("消息", "message"),
    ("事件", "event"),
    ("限量", "rate_limit"),
    ("限流", "rate_limit"),
]


def estimate_token_count(text: str) -> int:
    """Estimate token count with a mixed-script heuristic.

    CJK characters ≈ 1 token each; Latin words ≈ tokens/3.5 ~ chars/2.5.
    The rough average factor of 4 works well for mixed Chinese/English code text.
    """
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿" or "぀" <= ch <= "ヿ")
    latin = len(text) - cjk
    return max(1, cjk + latin // 3)


def truncate_facts_to_budget(
    facts: list[dict[str, Any]],
    *,
    max_tokens: int,
    question: str = "",
    prompt_overhead: int = 300,
) -> list[dict[str, Any]]:
    """Greedily truncate facts to fit within a token budget.

    Facts are assumed to be pre-sorted by relevance (best first).
    Returns the facts that fit, keeping the highest-ranked ones.
    Logs a warning when truncation occurs.
    """
    if not facts:
        return facts

    budget = max_tokens - prompt_overhead - estimate_token_count(question)
    if budget <= 0:
        budget = max_tokens // 2  # fallback: half the total budget

    kept: list[dict[str, Any]] = []
    used = 0
    for fact in facts:
        fact_tokens = estimate_token_count(fact.get("title", "")) + estimate_token_count(fact.get("content", ""))
        if used + fact_tokens <= budget:
            kept.append(fact)
            used += fact_tokens
        elif not kept:
            # Always keep at least the first fact even if it exceeds budget
            kept.append(fact)
            logger.warning(
                "Single fact exceeds token budget (%d > %d). Consider increasing AI_RAG_MAX_CONTEXT_TOKENS.",
                fact_tokens,
                budget,
            )
            break
        else:
            logger.warning(
                "Truncated RAG context: %d/%d facts fit within %d token budget (used %d).",
                len(kept),
                len(facts),
                max_tokens,
                used,
            )
            break

    return kept


def jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute Jaccard similarity on whitespace-normalized token sets."""
    tokens_a = set(text_a.split())
    tokens_b = set(text_b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def mmr_rerank(
    facts: list[dict[str, Any]],
    *,
    query: str,
    lambda_param: float = 0.7,
    top_k: int,
) -> list[dict[str, Any]]:
    """Maximum Marginal Relevance reranking for diversity.

    Selects facts that are both relevant to the query (via BM25 score) and
    dissimilar from already-selected facts (via Jaccard similarity).

    Arguments:
        facts: Pre-retrieved facts with 'score' (lower BM25 = better) and 'content'.
        query: The user's question.
        lambda_param: Balance between relevance (1.0 = BM25-only) and diversity (0.0 = diversity-only).
        top_k: Number of facts to return after reranking.

    Returns:
        Reranked subset of facts.
    """
    if not facts or len(facts) <= top_k:
        return facts

    # Normalize BM25 scores: lower is better → invert so higher = better
    scores = [float(f.get("score", 0)) for f in facts]
    min_score = min(scores)
    max_score = max(scores)
    if max_score > min_score:
        normalized = [(s - min_score) / (max_score - min_score) for s in scores]
        # Invert BM25 (lower = better) and scale to [0, 1]
        relevance = [1.0 - ns for ns in normalized]
    else:
        relevance = [1.0 / len(facts)] * len(facts)

    # Concatenate title + content for Jaccard comparison
    texts = [f"{f.get('title', '')} {f.get('content', '')}" for f in facts]

    selected: list[int] = []
    candidates = list(range(len(facts)))

    # Pick the most relevant fact first
    first = max(candidates, key=lambda i: relevance[i])
    selected.append(first)
    candidates.remove(first)

    while len(selected) < top_k and candidates:
        best_candidate = max(
            candidates,
            key=lambda i: lambda_param * relevance[i]
            - (1.0 - lambda_param) * max(jaccard_similarity(texts[i], texts[s]) for s in selected),
        )
        selected.append(best_candidate)
        candidates.remove(best_candidate)

    return [facts[i] for i in selected]


def expand_query_rule_based(question: str) -> list[str]:
    """Expand a question into multiple FTS5 query variants.

    Returns a list of FTS5-compatible MATCH strings. The caller should OR
    them together or run multiple searches and merge results.
    """
    # Detect Chinese tokens and add English synonyms
    expanded_tokens: list[str] = []
    for chinese, english in _SYNONYM_PAIRS:
        if chinese in question and english not in question:
            expanded_tokens.append(english)
        if english in question and chinese not in question:
            expanded_tokens.append(chinese)

    if expanded_tokens:
        # Build a secondary FTS5 query string from the synonym tokens
        synonym_query = " OR ".join(f'"{t}"' for t in expanded_tokens)
        return [synonym_query]

    return []


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def build_messages_with_history(
    *,
    system_prompt: str,
    user_prompt: str,
    history_messages: list[dict[str, Any]],
    max_turns: int,
) -> list[dict[str, str]]:
    """Build a messages list for Ollama with conversation history.

    Args:
        system_prompt: The static system prompt.
        user_prompt: The current user prompt (with RAG facts).
        history_messages: Prior messages from the session, ordered oldest-first.
        max_turns: Max number of previous user+assistant *pairs* to include.

    Returns:
        List of messages ready for Ollama's /api/chat endpoint.
    """
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

    if history_messages and max_turns > 0:
        # Take the last N user+assistant pairs
        pairs: list[tuple[dict, dict]] = []
        i = 0
        while i < len(history_messages):
            if history_messages[i]["role"] == "user" and i + 1 < len(history_messages):
                if history_messages[i + 1]["role"] == "assistant":
                    pairs.append((history_messages[i], history_messages[i + 1]))
                    i += 2
                    continue
            i += 1

        # Keep only the last max_turns pairs
        recent_pairs = pairs[-max_turns:] if max_turns > 0 else []

        for user_msg, assistant_msg in recent_pairs:
            # History user message: just the question (no RAG facts re-attached)
            messages.append({"role": "user", "content": str(user_msg["content"])})
            # History assistant message: just the answer
            messages.append({"role": "assistant", "content": str(assistant_msg["content"])})

    # Current user message with RAG context
    messages.append({"role": "user", "content": user_prompt})
    return messages


def hybrid_score(bm25_score: float, vector_score: float, alpha: float = 0.7) -> float:
    """Combine BM25 and vector similarity scores.

    Args:
        bm25_score: Raw BM25 score (lower = better, negative).
        vector_score: Cosine similarity (higher = better, 0-1).
        alpha: Weight for BM25 (0-1). alpha=0.7 means 70% BM25, 30% vector.

    Returns:
        Combined score where higher is better.
    """
    # Normalize BM25: lower (more negative) is better in FTS5
    # We invert so higher = better for both
    bm25_normalized = 1.0 / (1.0 + abs(bm25_score)) if bm25_score < 0 else 0.5
    return alpha * bm25_normalized + (1.0 - alpha) * vector_score
