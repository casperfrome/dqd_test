import hashlib
import json
import re
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import sqlite3

from app.core.config import Settings
from app.core.exceptions import AppError
from app.core.utils import utc_now_iso
from app.db.connection import create_connection
from app.repositories import ai_chat as ai_repo
from app.services.database_catalog import inspect_databases
from app.services.ollama_client import OllamaError, chat_with_ollama, get_embedding, get_ollama_health, stream_chat_with_ollama
from app.services.rag_utils import (
    build_messages_with_history,
    estimate_token_count,
    expand_query_rule_based,
    mmr_rerank,
    truncate_facts_to_budget,
)


INTERNAL_AI_SAMPLE_TABLES = {
    "ai_database_facts",
    "ai_database_fact_fts",
    "ai_chat_sessions",
    "ai_chat_messages",
    "ai_chat_events",
}

SYSTEM_PROMPT = """
你是 FootballDomain 项目的数据库 AI 助手。
你必须用中文回答，回答要结构化、条理清晰。

## 规则
- 你只能依据提供的 RAG 数据库事实回答；如果事实不足以支持结论，要明确说明当前数据库事实不足以判断并列出缺少什么信息。
- 不要编造不存在的表、字段、关系或样例数据。
- 不要生成会被执行的写入、更新或删除语句；如需给 SQL 示例，只能给只读 SELECT 示例。
- 回答中引用事实时，必须标注 fact_id，格式：[fact_id=N]。

## 示例
问：users 表有哪些字段？
答：users 表包含以下字段：
- id (INTEGER, 主键) [fact_id=3]
- username (TEXT, NOT NULL) [fact_id=5]
- email (TEXT) [fact_id=7]
""".strip()


def rebuild_database_facts(connection: sqlite3.Connection) -> dict[str, Any]:
    generated_at = utc_now_iso()
    new_facts = _build_facts_from_catalog(generated_at)
    new_hashes = {f["content_hash"] for f in new_facts}

    existing_hashes = ai_repo.get_existing_hashes(connection)

    inserted = 0
    for fact in new_facts:
        if fact["content_hash"] not in existing_hashes:
            ai_repo.insert_fact(connection, **fact)
            inserted += 1

    stale_hashes = existing_hashes - new_hashes
    if stale_hashes:
        ai_repo.delete_facts_by_hashes(connection, stale_hashes)

    connection.commit()

    return {
        "fact_count": len(new_facts),
        "new_facts": inserted,
        "stale_removed": len(stale_hashes),
        "rebuilt_at": generated_at,
    }


def ensure_database_facts_ready(connection: sqlite3.Connection, settings: Settings) -> None:
    needs_rebuild = False
    if ai_repo.count_facts(connection) == 0:
        needs_rebuild = True
    else:
        latest = ai_repo.get_latest_fact_updated_at(connection)
        if not latest:
            needs_rebuild = True
        else:
            try:
                latest_datetime = datetime.fromisoformat(latest)
            except ValueError:
                needs_rebuild = True
            else:
                if latest_datetime.tzinfo is None:
                    latest_datetime = latest_datetime.replace(tzinfo=timezone.utc)
                age_seconds = (datetime.now(timezone.utc) - latest_datetime).total_seconds()
                if age_seconds > settings.ai_fact_refresh_ttl_seconds:
                    needs_rebuild = True

    if needs_rebuild:
        rebuild_database_facts(connection)

    # Always backfill missing embeddings when enabled — covers the case where
    # embeddings were toggled on after facts were already built, or prior
    # embedding computation was interrupted.
    if settings.ai_embedding_enabled:
        _compute_embeddings_for_all_facts(connection, settings)


def answer_database_question(
    connection: sqlite3.Connection,
    settings: Settings,
    *,
    question: str,
    session_public_id: str | None,
    current_user: dict | None,
    client_id: str | None,
) -> dict[str, Any]:
    normalized_question = question.strip()
    if not normalized_question:
        raise AppError(status_code=422, message="Question is required.")

    ensure_database_facts_ready(connection, settings)
    owner_user_id, client_id_hash = _resolve_actor(current_user, client_id)
    session = _get_or_create_session(
        connection,
        session_public_id=session_public_id,
        owner_user_id=owner_user_id,
        client_id_hash=client_id_hash,
        question=normalized_question,
    )
    facts = retrieve_database_facts(connection, normalized_question, limit=settings.ai_rag_top_k, settings=settings)
    facts = truncate_facts_to_budget(
        facts,
        max_tokens=settings.ai_rag_max_context_tokens,
        question=normalized_question,
    )
    fact_ids = [int(fact["id"]) for fact in facts]
    created_at = utc_now_iso()
    user_message = ai_repo.insert_message(
        connection,
        session_id=int(session["id"]),
        role="user",
        content=normalized_question,
        retrieved_fact_ids=[],
        created_at=created_at,
    )

    # Load history and build multi-turn messages
    history = ai_repo.list_messages(connection, int(session["id"]))
    user_prompt = _build_user_prompt(normalized_question, facts)
    messages = build_messages_with_history(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        history_messages=[m for m in history if m["id"] != user_message["id"]],
        max_turns=settings.ai_chat_history_max_turns,
    )

    started_at = time.perf_counter()
    try:
        answer = chat_with_ollama(
            base_url=settings.ollama_base_url,
            model=settings.ai_chat_model,
            messages=messages,
        )
    except OllamaError as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        ai_repo.insert_event(
            connection,
            event_type="chat_completion",
            session_id=int(session["id"]),
            message_id=int(user_message["id"]),
            actor_user_id=owner_user_id,
            model=settings.ai_chat_model,
            retrieved_fact_ids=fact_ids,
            duration_ms=duration_ms,
            status="error",
            error_message=str(exc)[:500],
            created_at=utc_now_iso(),
        )
        connection.commit()
        raise AppError(status_code=502, message=str(exc)) from exc

    assistant_message = ai_repo.insert_message(
        connection,
        session_id=int(session["id"]),
        role="assistant",
        content=answer,
        retrieved_fact_ids=fact_ids,
        created_at=utc_now_iso(),
    )
    duration_ms = int((time.perf_counter() - started_at) * 1000)
    ai_repo.insert_event(
        connection,
        event_type="chat_completion",
        session_id=int(session["id"]),
        message_id=int(assistant_message["id"]),
        actor_user_id=owner_user_id,
        model=settings.ai_chat_model,
        retrieved_fact_ids=fact_ids,
        duration_ms=duration_ms,
        status="success",
        error_message=None,
        created_at=utc_now_iso(),
    )
    return {
        "session_id": session["public_id"],
        "user_message_id": user_message["id"],
        "assistant_message_id": assistant_message["id"],
        "answer": answer,
        "sources": [_source_from_fact(fact) for fact in facts],
    }


def stream_database_question_events(
    settings: Settings,
    *,
    question: str,
    session_public_id: str | None,
    current_user: dict | None,
    client_id: str | None,
    thinking_enabled: bool,
) -> Iterator[str]:
    connection = create_connection(settings)
    started_at = time.perf_counter()
    session: dict[str, Any] | None = None
    user_message: dict[str, Any] | None = None
    owner_user_id: int | None = None
    fact_ids: list[int] = []
    input_token_count = 0
    output_token_count = 0
    answer_parts: list[str] = []
    thinking_parts: list[str] = []
    try:
        normalized_question = question.strip()
        if not normalized_question:
            raise AppError(status_code=422, message="Question is required.")

        ensure_database_facts_ready(connection, settings)
        owner_user_id, client_id_hash = _resolve_actor(current_user, client_id)
        session = _get_or_create_session(
            connection,
            session_public_id=session_public_id,
            owner_user_id=owner_user_id,
            client_id_hash=client_id_hash,
            question=normalized_question,
        )
        facts = retrieve_database_facts(connection, normalized_question, limit=settings.ai_rag_top_k, settings=settings)
        facts = truncate_facts_to_budget(
            facts,
            max_tokens=settings.ai_rag_max_context_tokens,
            question=normalized_question,
        )
        fact_ids = [int(fact["id"]) for fact in facts]
        user_message = ai_repo.insert_message(
            connection,
            session_id=int(session["id"]),
            role="user",
            content=normalized_question,
            retrieved_fact_ids=[],
            thinking_enabled=thinking_enabled,
            created_at=utc_now_iso(),
        )
        connection.commit()

        sources = [_source_from_fact(fact) for fact in facts]
        yield sse_event(
            "session",
            {
                "session_id": session["public_id"],
                "user_message_id": user_message["id"],
                "thinking_enabled": thinking_enabled,
            },
        )
        yield sse_event("sources", {"sources": sources})

        # Load history and build multi-turn messages
        history = ai_repo.list_messages(connection, int(session["id"]))
        user_prompt = _build_user_prompt(normalized_question, facts)
        messages = build_messages_with_history(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            history_messages=[m for m in history if m["id"] != user_message["id"]],
            max_turns=settings.ai_chat_history_max_turns,
        )

        for event in stream_chat_with_ollama(
            base_url=settings.ollama_base_url,
            model=settings.ai_chat_model,
            messages=messages,
            thinking_enabled=thinking_enabled,
        ):
            if event["type"] == "thinking_delta":
                thinking_parts.append(str(event["delta"]))
                if thinking_enabled:
                    yield sse_event("thinking_delta", {"delta": event["delta"]})
            elif event["type"] == "content_delta":
                answer_parts.append(str(event["delta"]))
                yield sse_event("content_delta", {"delta": event["delta"]})
            elif event["type"] == "done":
                input_token_count = int(event.get("input_token_count") or 0)
                output_token_count = int(event.get("output_token_count") or 0)

        answer = "".join(answer_parts).strip()
        thinking_content = "".join(thinking_parts).strip() if thinking_enabled else ""
        assistant_message = ai_repo.insert_message(
            connection,
            session_id=int(session["id"]),
            role="assistant",
            content=answer,
            retrieved_fact_ids=fact_ids,
            thinking_enabled=thinking_enabled,
            thinking_content=thinking_content,
            input_token_count=input_token_count,
            output_token_count=output_token_count,
            created_at=utc_now_iso(),
        )
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        ai_repo.insert_event(
            connection,
            event_type="chat_completion",
            session_id=int(session["id"]),
            message_id=int(assistant_message["id"]),
            actor_user_id=owner_user_id,
            model=settings.ai_chat_model,
            retrieved_fact_ids=fact_ids,
            thinking_enabled=thinking_enabled,
            input_token_count=input_token_count,
            output_token_count=output_token_count,
            duration_ms=duration_ms,
            status="success",
            error_message=None,
            created_at=utc_now_iso(),
        )
        connection.commit()
        yield sse_event(
            "done",
            {
                "session_id": session["public_id"],
                "assistant_message_id": assistant_message["id"],
                "thinking_enabled": thinking_enabled,
                "input_token_count": input_token_count,
                "output_token_count": output_token_count,
                "sources": sources,
            },
        )
    except (AppError, OllamaError) as exc:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        if session is not None and user_message is not None:
            # Persist any partial assistant content as a "failed" assistant message,
            # so the next turn's history pairing stays consistent and the user can
            # see what was generated before the error.
            partial_answer = "".join(answer_parts).strip()
            try:
                if partial_answer:
                    ai_repo.insert_message(
                        connection,
                        session_id=int(session["id"]),
                        role="assistant",
                        content=f"[生成中断] {partial_answer}\n\n错误：{str(exc)[:200]}",
                        retrieved_fact_ids=fact_ids,
                        thinking_enabled=thinking_enabled,
                        input_token_count=input_token_count,
                        output_token_count=output_token_count,
                        created_at=utc_now_iso(),
                    )
            except sqlite3.Error:
                pass
            ai_repo.insert_event(
                connection,
                event_type="chat_completion",
                session_id=int(session["id"]),
                message_id=int(user_message["id"]),
                actor_user_id=owner_user_id,
                model=settings.ai_chat_model,
                retrieved_fact_ids=fact_ids,
                thinking_enabled=thinking_enabled,
                input_token_count=input_token_count,
                output_token_count=output_token_count,
                duration_ms=duration_ms,
                status="error",
                error_message=str(exc)[:500],
                created_at=utc_now_iso(),
            )
            connection.commit()
        else:
            connection.rollback()
        yield sse_event("error", {"message": str(exc)})
    except Exception as exc:
        connection.rollback()
        yield sse_event("error", {"message": f"AI streaming chat failed: {exc}"})
    finally:
        connection.close()


def sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _hybrid_rerank(
    connection: sqlite3.Connection,
    settings: Settings,
    question: str,
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rerank facts using hybrid BM25 + embedding similarity scores."""
    from app.services.rag_utils import cosine_similarity, hybrid_score

    try:
        query_embedding = get_embedding(
            base_url=settings.ollama_base_url,
            model=settings.ai_embedding_model,
            text=question,
        )
    except OllamaError:
        return facts  # fallback: keep BM25 order

    fact_ids = [int(f["id"]) for f in facts]
    stored = ai_repo.get_embeddings_for_facts(connection, fact_ids)

    for fact in facts:
        emb = stored.get(int(fact["id"]))
        if emb:
            vec_score = cosine_similarity(query_embedding, emb)
            fact["hybrid_score"] = hybrid_score(
                float(fact.get("score", 0)),
                vec_score,
                alpha=settings.ai_hybrid_alpha,
            )
        else:
            fact["hybrid_score"] = hybrid_score(float(fact.get("score", 0)), 0.0, alpha=1.0)

    facts.sort(key=lambda f: float(f.get("hybrid_score", 0)), reverse=True)
    return facts


def _compute_embeddings_for_all_facts(connection: sqlite3.Connection, settings: Settings) -> None:
    """Compute and store embeddings for facts that don't have one yet.

    Tolerates transient Ollama failures up to a small threshold before giving up,
    so a single network blip doesn't permanently leave embeddings empty.
    """
    rows = connection.execute(
        "SELECT id, title, content FROM ai_database_facts WHERE embedding_json = ''"
    ).fetchall()

    consecutive_failures = 0
    max_consecutive_failures = 3
    updated = 0
    for row in rows:
        text = f"{row['title']}\n{row['content']}"
        try:
            embedding = get_embedding(
                base_url=settings.ollama_base_url,
                model=settings.ai_embedding_model,
                text=text[:2000],
            )
            ai_repo.update_embedding(connection, int(row["id"]), json.dumps(embedding))
            consecutive_failures = 0
            updated += 1
        except OllamaError:
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                break

    if updated:
        connection.commit()


def retrieve_database_facts(connection: sqlite3.Connection, question: str, *, limit: int, settings: Settings | None = None) -> list[dict[str, Any]]:
    over_limit = limit * 2
    all_facts: list[dict[str, Any]] = []

    match_query = _to_fts_query(question)
    if match_query:
        try:
            all_facts = ai_repo.search_facts(connection, match_query, limit=over_limit)
        except sqlite3.Error:
            pass

    # Try synonym-expanded queries as supplementary
    extra_queries = expand_query_rule_based(question)
    for eq in extra_queries:
        try:
            extra = ai_repo.search_facts(connection, eq, limit=over_limit)
            seen = {f["id"] for f in all_facts}
            all_facts.extend(f for f in extra if f["id"] not in seen)
        except sqlite3.Error:
            continue

    if not all_facts:
        all_facts = ai_repo.list_recent_facts(connection, limit=over_limit)

    # Hybrid retrieval: fuse BM25 with embedding similarity
    if settings and settings.ai_embedding_enabled and all_facts:
        all_facts = _hybrid_rerank(connection, settings, question, all_facts)

    # MMR diversity rerank: select top_k diverse and relevant facts
    return mmr_rerank(all_facts, query=question, lambda_param=0.7, top_k=limit)


def list_chat_sessions(
    connection: sqlite3.Connection,
    *,
    current_user: dict | None,
    client_id: str | None,
) -> list[dict[str, Any]]:
    owner_user_id, client_id_hash = _resolve_actor(current_user, client_id)
    if owner_user_id is not None:
        sessions = ai_repo.list_sessions_for_owner(connection, owner_user_id)
    else:
        sessions = ai_repo.list_sessions_for_client(connection, str(client_id_hash))
    return [_serialize_session(session) for session in sessions]


def get_chat_session_detail(
    connection: sqlite3.Connection,
    *,
    session_public_id: str,
    current_user: dict | None,
    client_id: str | None,
) -> dict[str, Any]:
    owner_user_id, client_id_hash = _resolve_actor(current_user, client_id)
    session = ai_repo.get_session_by_public_id(connection, session_public_id)
    if not session or not _session_belongs_to_actor(session, owner_user_id, client_id_hash):
        raise AppError(status_code=404, message="AI chat session not found.")
    messages = []
    for message in ai_repo.list_messages(connection, int(session["id"])):
        facts = ai_repo.get_facts_by_ids(connection, [int(fact_id) for fact_id in message["retrieved_fact_ids"]])
        messages.append(
            {
                "id": message["id"],
                "role": message["role"],
                "content": message["content"],
                "thinking_enabled": message["thinking_enabled"],
                "thinking_content": message["thinking_content"],
                "input_token_count": message["input_token_count"],
                "output_token_count": message["output_token_count"],
                "retrieved_fact_ids": message["retrieved_fact_ids"],
                "sources": [_source_from_fact(fact) for fact in facts],
                "created_at": message["created_at"],
            },
        )
    return {**_serialize_session(session), "messages": messages}


def check_ollama_health(settings: Settings) -> dict[str, Any]:
    health = get_ollama_health(base_url=settings.ollama_base_url, model=settings.ai_chat_model)
    return {
        "ok": bool(health["ok"]),
        "model": settings.ai_chat_model,
        "base_url": settings.ollama_base_url,
        "error": health.get("error"),
        "available_models": health.get("available_models", []),
    }


def _build_facts_from_catalog(generated_at: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for database in inspect_databases():
        database_path = str(database["path"])
        facts.append(
            _fact(
                source_database_path=database_path,
                source_table_name=None,
                source_column_name=None,
                fact_type="database",
                title=f"数据库 {database['name']}",
                content=(
                    f"数据库文件 {database['name']}，相对路径 {database_path}，"
                    f"状态 {database['status']}，大小 {database['size_bytes']} 字节，"
                    f"包含 {database['table_count']} 张业务表。"
                ),
                metadata={"database": database},
                generated_at=generated_at,
            ),
        )
        for table in database["tables"]:
            table_name = str(table["name"])
            column_names = [str(column["name"]) for column in table["columns"]]
            facts.append(
                _fact(
                    source_database_path=database_path,
                    source_table_name=table_name,
                    source_column_name=None,
                    fact_type="table",
                    title=f"表 {table_name}",
                    content=(
                        f"表 {table_name}：{table['comment']} 行数 {table['row_count']}。"
                        f"字段包括：{', '.join(column_names) or '无字段'}。"
                    ),
                    metadata={"row_count": table["row_count"], "columns": column_names},
                    generated_at=generated_at,
                ),
            )
            for column in table["columns"]:
                constraints = []
                if column["primary_key"]:
                    constraints.append("主键")
                if column["not_null"]:
                    constraints.append("非空")
                facts.append(
                    _fact(
                        source_database_path=database_path,
                        source_table_name=table_name,
                        source_column_name=str(column["name"]),
                        fact_type="column",
                        title=f"字段 {table_name}.{column['name']}",
                        content=(
                            f"字段 {table_name}.{column['name']}：{column['comment']} "
                            f"类型 {column['type'] or '未声明'}，"
                            f"约束 {'、'.join(constraints) if constraints else '无特殊约束'}，"
                            f"默认值 {column['default_value'] if column['default_value'] is not None else '无'}。"
                        ),
                        metadata=column,
                        generated_at=generated_at,
                    ),
                )
            for index in table["indexes"]:
                facts.append(
                    _fact(
                        source_database_path=database_path,
                        source_table_name=table_name,
                        source_column_name=None,
                        fact_type="index",
                        title=f"索引 {index['name']}",
                        content=(
                            f"表 {table_name} 的索引 {index['name']}，"
                            f"字段 {', '.join(index['columns']) or '无'}，"
                            f"{'唯一索引' if index['unique'] else '非唯一索引'}，来源 {index['origin']}。"
                        ),
                        metadata=index,
                        generated_at=generated_at,
                    ),
                )
            for foreign_key in table["foreign_keys"]:
                facts.append(
                    _fact(
                        source_database_path=database_path,
                        source_table_name=table_name,
                        source_column_name=str(foreign_key["from_column"]),
                        fact_type="foreign_key",
                        title=f"外键 {table_name}.{foreign_key['from_column']}",
                        content=(
                            f"表 {table_name} 字段 {foreign_key['from_column']} 外键关联 "
                            f"{foreign_key['to_table']}.{foreign_key['to_column'] or '未知字段'}，"
                            f"更新策略 {foreign_key['on_update']}，删除策略 {foreign_key['on_delete']}。"
                        ),
                        metadata=foreign_key,
                        generated_at=generated_at,
                    ),
                )
            if table_name not in INTERNAL_AI_SAMPLE_TABLES and table["sample_rows"]:
                facts.append(
                    _fact(
                        source_database_path=database_path,
                        source_table_name=table_name,
                        source_column_name=None,
                        fact_type="sample_rows",
                        title=f"样例数据 {table_name}",
                        content=f"表 {table_name} 的随机样例数据：{json.dumps(table['sample_rows'], ensure_ascii=False)}",
                        metadata={"sample_rows": table["sample_rows"]},
                        generated_at=generated_at,
                    ),
                )
    return facts


def _fact(
    *,
    source_database_path: str,
    source_table_name: str | None,
    source_column_name: str | None,
    fact_type: str,
    title: str,
    content: str,
    metadata: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "source_database_path": source_database_path,
                "source_table_name": source_table_name,
                "source_column_name": source_column_name,
                "fact_type": fact_type,
                "title": title,
                "content": content,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()
    return {
        "source_database_path": source_database_path,
        "source_table_name": source_table_name,
        "source_column_name": source_column_name,
        "fact_type": fact_type,
        "title": title,
        "content": content,
        "metadata": metadata,
        "content_hash": content_hash,
        "generated_at": generated_at,
        "updated_at": generated_at,
    }


def _resolve_actor(current_user: dict | None, client_id: str | None) -> tuple[int | None, str | None]:
    if current_user:
        return int(current_user["id"]), None
    if not client_id or not client_id.strip():
        raise AppError(status_code=400, message="X-AI-Client-Id header is required for anonymous AI chat.")
    return None, hashlib.sha256(client_id.strip().encode("utf-8")).hexdigest()


def _get_or_create_session(
    connection: sqlite3.Connection,
    *,
    session_public_id: str | None,
    owner_user_id: int | None,
    client_id_hash: str | None,
    question: str,
) -> dict[str, Any]:
    if session_public_id:
        session = ai_repo.get_session_by_public_id(connection, session_public_id)
        if not session or not _session_belongs_to_actor(session, owner_user_id, client_id_hash):
            raise AppError(status_code=404, message="AI chat session not found.")
        return session
    return ai_repo.create_session(
        connection,
        public_id=str(uuid.uuid4()),
        owner_user_id=owner_user_id,
        client_id_hash=client_id_hash,
        title=_title_from_question(question),
        created_at=utc_now_iso(),
    )


def _session_belongs_to_actor(session: dict[str, Any], owner_user_id: int | None, client_id_hash: str | None) -> bool:
    if owner_user_id is not None:
        return session["owner_user_id"] == owner_user_id
    return session["owner_user_id"] is None and session["client_id_hash"] == client_id_hash


def _title_from_question(question: str) -> str:
    compact = " ".join(question.split())
    return compact[:48] or "数据库 AI 会话"


def _to_fts_query(question: str) -> str:
    # Extract identifiers (including compound names) and CJK characters
    tokens = re.findall(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]", question)
    # Split compound identifiers into sub-tokens (e.g. user_id \u2192 user_id + user + id)
    expanded: list[str] = []
    for token in tokens[:32]:
        expanded.append(token)
        expanded.extend(part for part in re.split(r"[_./:-]+", token) if part and part != token)
    unique = list(dict.fromkeys(expanded))[:48]
    return " OR ".join(f'"{token.replace(chr(34), chr(34) + chr(34))}"' for token in unique)


def _build_user_prompt(question: str, facts: list[dict[str, Any]]) -> str:
    if facts:
        # Check average BM25 score for confidence hint
        scores = [float(f.get("score", 0)) for f in facts]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        confidence = "高置信度" if avg_score < -2.0 else "近似匹配"
        header = f"RAG 数据库事实（{confidence}）："
        context = "\n\n".join(
            f"[fact_id={fact['id']}] {fact['title']}\n{fact['content']}"
            for fact in facts
        )
    else:
        header = "RAG 数据库事实："
        context = "没有检索到相关数据库事实。"
    return f"用户问题：{question}\n\n{header}\n{context}\n\n请根据以上事实回答。请在回答中引用所使用的 fact_id。"


def _source_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    content = str(fact["content"])
    return {
        "fact_id": fact["id"],
        "fact_type": fact["fact_type"],
        "title": fact["title"],
        "source_database_path": fact["source_database_path"],
        "source_table_name": fact["source_table_name"],
        "source_column_name": fact["source_column_name"],
        "snippet": content[:220],
        "score": fact.get("score"),
    }


def _serialize_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session["public_id"],
        "title": session["title"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
    }
