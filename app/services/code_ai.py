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
from app.repositories import ai_code as ai_repo
from app.services.code_catalog import list_code_files, read_code_file
from app.services.ollama_client import OllamaError, chat_with_ollama, get_embedding, get_ollama_health, stream_chat_with_ollama
from app.services.rag_utils import (
    build_messages_with_history,
    estimate_token_count,
    expand_query_rule_based,
    mmr_rerank,
    truncate_facts_to_budget,
)


CHUNK_LINE_COUNT = 120
CHUNK_OVERLAP = 20

SYSTEM_PROMPT = """
你是 FootballDomain 项目的代码 AI 助手，必须用中文回答，回答要结构化、条理清晰。

## 规则
- 你只能依据提供的 RAG 代码片段回答；如果片段不足以支持结论，要明确说明当前代码事实不足以判断并列出缺少什么信息。
- 回答涉及实现位置时，必须引用文件路径和行号范围。不要编造不存在的文件、函数、组件或接口。
- 不要生成会修改项目的命令；如需给示例代码，应说明它只是建议。
- 回答中引用事实时，必须标注 fact_id，格式：[fact_id=N]。
- 区分代码中已存在和这是我基于推理的建议。

## 示例
问：认证逻辑在哪里实现的？
答：认证逻辑主要在以下文件中：
- app/api/auth.py:25-45 定义了登录端点 [fact_id=12]
- app/services/auth_service.py:10-80 实现了密码验证 [fact_id=15]
""".strip()


def rebuild_code_facts(connection: sqlite3.Connection) -> dict[str, Any]:
    generated_at = utc_now_iso()
    new_facts = _build_facts_from_code(generated_at)
    new_hashes = {f["content_hash"] for f in new_facts}

    existing_hashes = ai_repo.get_existing_hashes(connection)

    # Insert new facts (hash not yet in DB)
    inserted = 0
    for fact in new_facts:
        if fact["content_hash"] not in existing_hashes:
            ai_repo.insert_fact(connection, **fact)
            inserted += 1

    # Remove stale facts (hash no longer in codebase)
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


def ensure_code_facts_ready(connection: sqlite3.Connection, settings: Settings) -> None:
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
        rebuild_code_facts(connection)

    # Always backfill missing embeddings when enabled — covers the case where
    # embeddings were toggled on after facts were already built, or prior
    # embedding computation was interrupted.
    if settings.ai_embedding_enabled:
        _compute_code_embeddings_for_all_facts(connection, settings)


def answer_code_question(
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

    ensure_code_facts_ready(connection, settings)
    owner_user_id, client_id_hash = _resolve_actor(current_user, client_id)
    session = _get_or_create_session(
        connection,
        session_public_id=session_public_id,
        owner_user_id=owner_user_id,
        client_id_hash=client_id_hash,
        question=normalized_question,
    )
    facts = retrieve_code_facts(connection, normalized_question, limit=settings.ai_rag_top_k, settings=settings)
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


def stream_code_question_events(
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

        ensure_code_facts_ready(connection, settings)
        owner_user_id, client_id_hash = _resolve_actor(current_user, client_id)
        session = _get_or_create_session(
            connection,
            session_public_id=session_public_id,
            owner_user_id=owner_user_id,
            client_id_hash=client_id_hash,
            question=normalized_question,
        )
        facts = retrieve_code_facts(connection, normalized_question, limit=settings.ai_rag_top_k, settings=settings)
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


def _hybrid_code_rerank(
    connection: sqlite3.Connection,
    settings: Settings,
    question: str,
    facts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rerank code facts using hybrid BM25 + embedding similarity scores."""
    from app.services.rag_utils import cosine_similarity, hybrid_score

    try:
        query_embedding = get_embedding(
            base_url=settings.ollama_base_url,
            model=settings.ai_embedding_model,
            text=question,
        )
    except OllamaError:
        return facts

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


def _compute_code_embeddings_for_all_facts(connection: sqlite3.Connection, settings: Settings) -> None:
    """Compute and store embeddings for code facts that don't have one yet.

    Tolerates transient Ollama failures up to a small threshold before giving up.
    """
    rows = connection.execute(
        "SELECT id, title, content FROM ai_code_facts WHERE embedding_json = ''"
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


def retrieve_code_facts(connection: sqlite3.Connection, question: str, *, limit: int, settings: Settings | None = None) -> list[dict[str, Any]]:
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
        all_facts = _hybrid_code_rerank(connection, settings, question, all_facts)

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


def _build_facts_from_code(generated_at: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for file_info in list_code_files():
        file_detail = read_code_file(str(file_info["path"]))
        content = str(file_detail["content"])
        lines = content.splitlines()
        if not lines:
            continue

        language = str(file_info["language"])
        if language == "python":
            facts.extend(_chunk_python_ast(file_info, file_detail, lines, generated_at))
        else:
            facts.extend(_chunk_fixed_window(file_info, file_detail, lines, generated_at))
    return facts


def _chunk_fixed_window(
    file_info: dict[str, Any],
    file_detail: dict[str, Any],
    lines: list[str],
    generated_at: str,
) -> list[dict[str, Any]]:
    """Fixed-window sliding chunking for non-Python files."""
    facts: list[dict[str, Any]] = []
    start_index = 0
    while start_index < len(lines):
        end_index = min(start_index + CHUNK_LINE_COUNT, len(lines))
        chunk_lines = lines[start_index:end_index]
        facts.append(
            _fact(
                source_file_path=str(file_info["path"]),
                language=str(file_info["language"]),
                start_line=start_index + 1,
                end_line=end_index,
                title=f"{file_info['path']}:{start_index + 1}-{end_index}",
                content="\n".join(chunk_lines),
                metadata={
                    "file": file_info,
                    "line_count": file_detail["line_count"],
                },
                generated_at=generated_at,
            ),
        )
        if end_index >= len(lines):
            break
        start_index = max(end_index - CHUNK_OVERLAP, start_index + 1)
    return facts


def _chunk_python_ast(
    file_info: dict[str, Any],
    file_detail: dict[str, Any],
    lines: list[str],
    generated_at: str,
) -> list[dict[str, Any]]:
    """AST-aware chunking: group by function/class boundaries for Python files."""
    import ast

    file_path = str(file_info["path"])
    facts: list[dict[str, Any]] = []
    source = "\n".join(lines)
    lineno_map: dict[int, int] = {}  # node end_lineno → next sibling start

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        # Fall back to fixed-window on parse errors
        return _chunk_fixed_window(file_info, file_detail, lines, generated_at)

    # Collect top-level nodes with their line ranges
    nodes: list[dict[str, Any]] = []
    import_lines_start: int | None = None
    import_lines_end: int | None = None

    for node in tree.body:
        start = node.lineno
        end = getattr(node, "end_lineno", start)

        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if import_lines_start is None:
                import_lines_start = start
            import_lines_end = max(import_lines_end or end, end)
            continue

        # Flush import block before first non-import node
        if import_lines_start is not None:
            nodes.append({
                "type": "imports",
                "start": import_lines_start,
                "end": import_lines_end,
                "name": "",
                "docstring": "",
            })
            import_lines_start = None
            import_lines_end = None

        name = ""
        docstring = ""
        if isinstance(node, ast.FunctionDef):
            name = node.name
            docstring = ast.get_docstring(node) or ""
        elif isinstance(node, ast.AsyncFunctionDef):
            name = node.name
            docstring = ast.get_docstring(node) or ""
        elif isinstance(node, ast.ClassDef):
            name = node.name
            docstring = ast.get_docstring(node) or ""

        nodes.append({
            "type": type(node).__name__,
            "start": start,
            "end": end,
            "name": name,
            "docstring": docstring,
        })

    # Flush trailing imports
    if import_lines_start is not None:
        nodes.append({
            "type": "imports",
            "start": import_lines_start,
            "end": import_lines_end,
            "name": "",
            "docstring": "",
        })

    # Group nodes into chunks respecting size limits
    current_chunk_start: int | None = None
    current_chunk_end: int | None = None
    chunk_names: list[str] = []
    chunk_docstrings: list[str] = []

    def _emit_chunk(start: int, end: int, names: list[str], docs: list[str]) -> None:
        if start > len(lines):
            return
        chunk_lines = lines[start - 1 : min(end, len(lines))]
        title = f"{file_path}:{start}-{min(end, len(lines))}"
        names_str = names[0] if len(names) == 1 else ", ".join(names[:3])
        if names_str:
            title = f"{title} ({names_str})"
        facts.append(
            _fact(
                source_file_path=file_path,
                language="python",
                start_line=start,
                end_line=min(end, len(lines)),
                title=title,
                content="\n".join(chunk_lines),
                metadata={
                    "file": file_info,
                    "line_count": file_detail["line_count"],
                    "function_name": names_str if names else "",
                    "docstring": "\n".join(docs) if docs else "",
                },
                generated_at=generated_at,
            ),
        )

    for node in nodes:
        node_lines = node["end"] - node["start"] + 1

        # If this single node exceeds chunk size, split it
        if node_lines > CHUNK_LINE_COUNT * 1.5:
            if current_chunk_start is not None:
                _emit_chunk(
                    current_chunk_start, current_chunk_end or current_chunk_start,
                    chunk_names, chunk_docstrings,
                )
            # Split large node with fixed-window
            start_line = node["start"]
            while start_line <= node["end"]:
                chunk_end = min(start_line + CHUNK_LINE_COUNT - 1, node["end"])
                chunk_lines_inner = lines[start_line - 1 : chunk_end]
                name_tag = f"{node['name']} pt{start_line}" if node["name"] else ""
                title = f"{file_path}:{start_line}-{chunk_end}"
                if name_tag:
                    title = f"{title} ({name_tag})"
                facts.append(
                    _fact(
                        source_file_path=file_path,
                        language="python",
                        start_line=start_line,
                        end_line=chunk_end,
                        title=title,
                        content="\n".join(chunk_lines_inner),
                        metadata={
                            "file": file_info,
                            "line_count": file_detail["line_count"],
                            "function_name": node["name"],
                            "class_name": "",
                            "docstring": node["docstring"],
                        },
                        generated_at=generated_at,
                    ),
                )
                if chunk_end >= node["end"]:
                    break
                start_line = max(chunk_end - CHUNK_OVERLAP + 1, start_line + 1)
            current_chunk_start = None
            current_chunk_end = None
            chunk_names = []
            chunk_docstrings = []
            continue

        # Start or extend a chunk
        if current_chunk_start is None:
            current_chunk_start = node["start"]
            current_chunk_end = node["end"]
        else:
            current_chunk_end = node["end"]

        if node["name"]:
            chunk_names.append(node["name"])
        if node["docstring"]:
            chunk_docstrings.append(node["docstring"])

        # Emit chunk if it's getting too large
        chunk_span = (current_chunk_end or 0) - (current_chunk_start or 0) + 1
        if chunk_span >= CHUNK_LINE_COUNT:
            _emit_chunk(current_chunk_start, current_chunk_end or current_chunk_start,
                        chunk_names, chunk_docstrings)
            current_chunk_start = None
            current_chunk_end = None
            chunk_names = []
            chunk_docstrings = []

    # Emit final chunk
    if current_chunk_start is not None:
        _emit_chunk(current_chunk_start, current_chunk_end or current_chunk_start,
                    chunk_names, chunk_docstrings)

    return facts


def _fact(
    *,
    source_file_path: str,
    language: str,
    start_line: int,
    end_line: int,
    title: str,
    content: str,
    metadata: dict[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "source_file_path": source_file_path,
                "language": language,
                "start_line": start_line,
                "end_line": end_line,
                "title": title,
                "content": content,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()
    return {
        "source_file_path": source_file_path,
        "language": language,
        "start_line": start_line,
        "end_line": end_line,
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
    return compact[:48] or "代码 AI 会话"


def _to_fts_query(question: str) -> str:
    # Extract identifiers (including compound names) and CJK characters
    tokens = re.findall(r"[A-Za-z0-9_./:-]+|[\u4e00-\u9fff]", question)
    expanded: list[str] = []
    for token in tokens[:32]:
        expanded.append(token)
        expanded.extend(part for part in re.split(r"[_./:-]+", token) if part and part != token)
    unique = list(dict.fromkeys(expanded))[:48]
    return " OR ".join(f'"{token.replace(chr(34), chr(34) + chr(34))}"' for token in unique)


def _build_user_prompt(question: str, facts: list[dict[str, Any]]) -> str:
    if facts:
        scores = [float(f.get("score", 0)) for f in facts]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        confidence = "高置信度" if avg_score < -2.0 else "近似匹配"
        header = f"RAG 代码片段（{confidence}）："
        context = "\n\n".join(
            (
                f"[fact_id={fact['id']}] {fact['source_file_path']}:{fact['start_line']}-{fact['end_line']}"
                f" ({fact['language']})\n{fact['content']}"
            )
            for fact in facts
        )
    else:
        header = "RAG 代码片段："
        context = "没有检索到相关代码事实。"
    return f"用户问题：{question}\n\n{header}\n{context}\n\n请根据以上代码事实回答。请在回答中引用文件路径、行号范围以及所使用的 fact_id。"


def _source_from_fact(fact: dict[str, Any]) -> dict[str, Any]:
    content = str(fact["content"])
    return {
        "fact_id": fact["id"],
        "source_file_path": fact["source_file_path"],
        "language": fact["language"],
        "start_line": fact["start_line"],
        "end_line": fact["end_line"],
        "title": fact["title"],
        "snippet": content[:260],
        "score": fact.get("score"),
    }


def _serialize_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session["public_id"],
        "title": session["title"],
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
    }
