from pathlib import Path
from typing import Any

from app.core.config import ROOT_DIR
from app.core.exceptions import AppError


SOURCE_ROOTS = {
    Path("app"),
    Path("frontend") / "src",
    Path("sql"),
    Path("tests"),
}

ROOT_TEXT_FILES = {
    Path("README.md"),
    Path("requirements.txt"),
    Path("frontend") / "README.md",
    Path("frontend") / "package.json",
    Path("frontend") / "index.html",
    Path("frontend") / "vite.config.ts",
    Path("frontend") / "eslint.config.mjs",
    Path("frontend") / "tsconfig.json",
    Path("frontend") / "tsconfig.app.json",
    Path("frontend") / "tsconfig.node.json",
}

EXCLUDED_DIRS = {
    ".git",
    ".idea",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "node_modules",
}

EXCLUDED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".pyc",
    ".pyo",
    ".zip",
    ".gz",
    ".tar",
    ".7z",
    ".exe",
    ".dll",
}

EXCLUDED_NAMES = {
    ".env",
    ".env.example",
    "package-lock.json",
}

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".json",
    ".css",
    ".html",
    ".md",
    ".sql",
    ".txt",
}

MAX_FILE_BYTES = 256 * 1024

LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "jsx",
    ".mjs": "javascript",
    ".json": "json",
    ".css": "css",
    ".html": "html",
    ".md": "markdown",
    ".sql": "sql",
    ".txt": "text",
}


def list_code_files(root: Path = ROOT_DIR) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if not path.is_file() or not is_code_file(path, root):
            continue
        try:
            relative_path = _relative_posix(path, root)
            stat = path.stat()
            content = read_code_file(relative_path, root=root)["content"]
        except (OSError, UnicodeDecodeError, AppError):
            continue
        files.append(
            {
                "path": relative_path,
                "name": path.name,
                "extension": path.suffix.lower(),
                "language": language_for_path(path),
                "size_bytes": stat.st_size,
                "line_count": _line_count(content),
            },
        )
    return sorted(files, key=lambda item: item["path"])


def inspect_code_catalog(root: Path = ROOT_DIR) -> dict[str, Any]:
    files = list_code_files(root)
    return {
        "files": files,
        "tree": build_file_tree(files),
        "file_count": len(files),
        "total_size_bytes": sum(int(file["size_bytes"]) for file in files),
    }


def read_code_file(path: str, *, root: Path = ROOT_DIR) -> dict[str, Any]:
    resolved = resolve_code_path(path, root=root)
    content = resolved.read_text(encoding="utf-8")
    return {
        "path": _relative_posix(resolved, root),
        "name": resolved.name,
        "extension": resolved.suffix.lower(),
        "language": language_for_path(resolved),
        "size_bytes": resolved.stat().st_size,
        "line_count": _line_count(content),
        "content": content,
    }


def resolve_code_path(path: str, *, root: Path = ROOT_DIR) -> Path:
    if not path or path.strip() != path:
        raise AppError(status_code=422, message="Code file path is required.")
    candidate = (root / path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise AppError(status_code=400, message="Path must stay inside the project.") from exc
    if not candidate.is_file() or not is_code_file(candidate, root):
        raise AppError(status_code=404, message="Code file not found or not readable.")
    return candidate


def is_code_file(path: Path, root: Path = ROOT_DIR) -> bool:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if path.stat().st_size > MAX_FILE_BYTES:
        return False
    if not _is_in_source_scope(relative):
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES and relative not in ROOT_TEXT_FILES:
        return False
    return _looks_like_text(path)


def language_for_path(path: Path) -> str:
    return LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "text")


def build_file_tree(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root_nodes: dict[str, dict[str, Any]] = {}
    for file in files:
        parts = str(file["path"]).split("/")
        current = root_nodes
        current_path: list[str] = []
        for index, part in enumerate(parts):
            current_path.append(part)
            if part not in current:
                current[part] = {
                    "name": part,
                    "path": "/".join(current_path),
                    "type": "file" if index == len(parts) - 1 else "directory",
                    "children": {},
                    "file": None,
                }
            node = current[part]
            if index == len(parts) - 1:
                node["type"] = "file"
                node["file"] = file
            current = node["children"]
    return _serialize_nodes(root_nodes)


def _serialize_nodes(nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    serialized = []
    for node in sorted(nodes.values(), key=lambda item: (item["type"] == "file", item["name"].lower())):
        children = _serialize_nodes(node["children"])
        serialized.append(
            {
                "name": node["name"],
                "path": node["path"],
                "type": node["type"],
                "children": children,
                "file": node["file"],
            },
        )
    return serialized


def _is_in_source_scope(relative: Path) -> bool:
    if relative in ROOT_TEXT_FILES:
        return True
    return any(relative == source_root or source_root in relative.parents for source_root in SOURCE_ROOTS)


def _looks_like_text(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return False
    if b"\x00" in chunk:
        return False
    try:
        chunk.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _line_count(content: str) -> int:
    if not content:
        return 0
    return len(content.splitlines())
