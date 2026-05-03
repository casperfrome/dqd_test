import { ChevronRight, File, Folder, FolderOpen } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import type { CodeTreeNode } from "../../api/types";

interface CodeFileTreeProps {
  nodes: CodeTreeNode[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
}

export function CodeFileTree({ nodes, selectedPath, onSelect }: CodeFileTreeProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    setExpanded(new Set(nodes.filter((node) => node.type === "directory").map((node) => node.path)));
  }, [nodes]);

  const toggle = (path: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderNode = (node: CodeTreeNode, depth = 0): ReactNode => {
    if (node.type === "file") {
      return (
        <button
          key={node.path}
          className={`code-file-row ${selectedPath === node.path ? "active" : ""}`}
          style={{ paddingLeft: 10 + depth * 14 }}
          onClick={() => onSelect(node.path)}
        >
          <File size={15} />
          <span>{node.name}</span>
        </button>
      );
    }
    const isOpen = expanded.has(node.path);
    return (
      <div className="code-tree-group" key={node.path}>
        <button
          className="code-folder-row"
          style={{ paddingLeft: 10 + depth * 14 }}
          onClick={() => toggle(node.path)}
        >
          <ChevronRight size={14} className={isOpen ? "open" : ""} />
          {isOpen ? <FolderOpen size={15} /> : <Folder size={15} />}
          <span>{node.name}</span>
        </button>
        {isOpen && node.children.map((child) => renderNode(child, depth + 1))}
      </div>
    );
  };

  return <div className="code-tree">{nodes.map((node) => renderNode(node))}</div>;
}
