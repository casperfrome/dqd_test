import { FileCode, RefreshCw, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { CodeCatalogResponse, CodeFileResponse, UserProfile } from "../../api/types";
import { databaseAccessLabels } from "../../utils/constants";
import { formatFileSize, getErrorMessage } from "../../utils/helpers";
import { EmptyState } from "../ui/EmptyState";
import { CodeAiPanel } from "./CodeAiPanel";
import { CodeFileTree } from "./CodeFileTree";

interface CodeQaViewProps {
  currentUser: UserProfile | null;
}

export function CodeQaView({ currentUser }: CodeQaViewProps) {
  const [catalog, setCatalog] = useState<CodeCatalogResponse | null>(null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<CodeFileResponse | null>(null);
  const [filter, setFilter] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [focusLine, setFocusLine] = useState<number | null>(null);

  const filteredFiles = useMemo(() => {
    const keyword = filter.trim().toLowerCase();
    if (!keyword) {
      return catalog?.files ?? [];
    }
    return (catalog?.files ?? []).filter((file) => file.path.toLowerCase().includes(keyword));
  }, [catalog, filter]);

  const loadFile = async (path: string, line?: number) => {
    setLoadingFile(true);
    setError(null);
    try {
      const file = await api.getCodeFile(path);
      setSelectedFilePath(file.path);
      setSelectedFile(file);
      setFocusLine(line ?? null);
    } catch (loadError) {
      setError(getErrorMessage(loadError));
    } finally {
      setLoadingFile(false);
    }
  };

  const loadCatalog = async () => {
    setLoadingCatalog(true);
    setError(null);
    try {
      const response = await api.getCodeCatalog();
      setCatalog(response);
      const nextPath =
        response.files.find((file) => file.path === selectedFilePath)?.path ??
        response.files[0]?.path ??
        null;
      setSelectedFilePath(nextPath);
      if (nextPath) {
        await loadFile(nextPath);
      } else {
        setSelectedFile(null);
      }
    } catch (loadError) {
      setCatalog(null);
      setSelectedFile(null);
      setError(getErrorMessage(loadError));
    } finally {
      setLoadingCatalog(false);
    }
  };

  useEffect(() => {
    void loadCatalog();
  }, [currentUser?.id]);

  useEffect(() => {
    if (focusLine === null) {
      return;
    }
    window.requestAnimationFrame(() => {
      document.querySelector(`[data-code-line="${focusLine}"]`)?.scrollIntoView({
        block: "center",
      });
    });
  }, [selectedFile?.path, focusLine]);

  if (!catalog) {
    return (
      <section className="single-panel">
        <EmptyState text={loadingCatalog ? "正在加载项目代码..." : "暂无代码目录数据，或当前账号没有查看权限。"} />
        {error && <p className="muted">{error}</p>}
        <button className="primary" onClick={() => void loadCatalog()}>
          <RefreshCw size={17} />
          重新加载
        </button>
      </section>
    );
  }

  return (
    <section className="code-page">
      <CodeAiPanel
        currentUser={currentUser}
        onOpenSource={(source) => void loadFile(source.source_file_path, source.start_line)}
      />

      <div className="code-workspace panel">
        <div className="section-title">
          <div>
            <h2>项目代码</h2>
            <p className="muted">
              {catalog.file_count} 个文件 · {formatFileSize(catalog.total_size_bytes)} · 权限：
              {databaseAccessLabels[catalog.access_level]}
            </p>
          </div>
          <div className="toolbar">
            <button className="ghost" type="button" disabled={loadingCatalog} onClick={() => void loadCatalog()}>
              <RefreshCw size={17} />
              刷新代码
            </button>
          </div>
        </div>

        {error && <div className="ai-status error">{error}</div>}

        <div className="code-browser">
          <aside className="code-tree-panel">
            <label className="code-search">
              <Search size={16} />
              <input
                value={filter}
                onChange={(event) => setFilter(event.target.value)}
                placeholder="搜索文件路径"
              />
            </label>
            {filter.trim() ? (
              <div className="code-file-results">
                {filteredFiles.map((file) => (
                  <button
                    key={file.path}
                    className={`code-file-row ${selectedFilePath === file.path ? "active" : ""}`}
                    onClick={() => void loadFile(file.path)}
                  >
                    <FileCode size={15} />
                    <span>{file.path}</span>
                  </button>
                ))}
                {filteredFiles.length === 0 && <EmptyState text="没有匹配的代码文件。" />}
              </div>
            ) : (
              <CodeFileTree
                nodes={catalog.tree}
                selectedPath={selectedFilePath}
                onSelect={(path) => void loadFile(path)}
              />
            )}
          </aside>

          <div className="code-editor-panel">
            <div className="code-tabbar">
              {selectedFile ? (
                <div className="code-tab active">
                  <FileCode size={15} />
                  <span>{selectedFile.path}</span>
                </div>
              ) : (
                <div className="code-tab">未选择文件</div>
              )}
              {selectedFile && (
                <span className="code-file-meta">
                  {selectedFile.language} · {selectedFile.line_count} 行 · {formatFileSize(selectedFile.size_bytes)}
                </span>
              )}
            </div>

            <div className="code-editor">
              {selectedFile ? (
                selectedFile.content.split(/\r?\n/).map((line, index) => {
                  const lineNumber = index + 1;
                  return (
                    <div
                      key={lineNumber}
                      className={`code-line ${focusLine === lineNumber ? "focused" : ""}`}
                      data-code-line={lineNumber}
                    >
                      <span className="code-line-number">{lineNumber}</span>
                      <code>{line || " "}</code>
                    </div>
                  );
                })
              ) : (
                <EmptyState text={loadingFile ? "正在加载代码..." : "请选择左侧文件查看内容。"} />
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
