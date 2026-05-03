import { Check, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import type { DatabaseAccessLevel, DatabaseCatalogResponse, DatabaseInfo, DatabaseTable, UserProfile } from "../../api/types";
import { databaseAccessLabels } from "../../utils/constants";
import { formatFileSize } from "../../utils/helpers";
import { EmptyState } from "../ui/EmptyState";
import { Metric } from "../ui/Metric";
import { DatabaseAiPanel } from "./DatabaseAiPanel";
import { SampleRowsTable } from "./SampleRowsTable";

interface DatabasesViewProps {
  catalog: DatabaseCatalogResponse | null;
  currentUser: UserProfile | null;
  selectedDatabase: DatabaseInfo | null;
  selectedTable: DatabaseTable | null;
  selectedDatabasePath: string | null;
  selectedTableName: string | null;
  onSelectDatabase: (path: string) => void;
  onSelectTable: (tableName: string) => void;
  onRefresh: () => Promise<void>;
  onUpdateAccess: (accessLevel: DatabaseAccessLevel) => Promise<void>;
}

export function DatabasesView({
  catalog,
  currentUser,
  selectedDatabase,
  selectedTable,
  selectedDatabasePath,
  selectedTableName,
  onSelectDatabase,
  onSelectTable,
  onRefresh,
  onUpdateAccess,
}: DatabasesViewProps) {
  const [draftAccess, setDraftAccess] = useState<DatabaseAccessLevel>(catalog?.access_level ?? "public");
  const isSuperAdmin = currentUser?.role === "super_admin";
  const databaseCount = catalog?.databases.length ?? 0;
  const tableCount = catalog?.databases.reduce((total, database) => total + database.table_count, 0) ?? 0;

  useEffect(() => {
    setDraftAccess(catalog?.access_level ?? "public");
  }, [catalog?.access_level]);

  if (!catalog) {
    return (
      <section className="single-panel">
        <EmptyState text="暂无数据库目录数据，或当前账号没有查看权限。" />
        <button className="primary" onClick={() => void onRefresh()}>
          <RefreshCw size={17} />
          重新加载
        </button>
      </section>
    );
  }

  return (
    <section className="database-page">
      <div className="database-summary panel">
        <Metric label="数据库文件" value={databaseCount} />
        <Metric label="数据表" value={tableCount} />
        <Metric label="访问权限" value={databaseAccessLabels[catalog.access_level]} />
        {isSuperAdmin && (
          <form
            className="access-control"
            onSubmit={(event) => {
              event.preventDefault();
              void onUpdateAccess(draftAccess);
            }}
          >
            <label>
              板块权限
              <select value={draftAccess} onChange={(event) => setDraftAccess(event.target.value as DatabaseAccessLevel)}>
                <option value="public">公开访问</option>
                <option value="authenticated">登录用户</option>
                <option value="super_admin">超级管理员</option>
              </select>
            </label>
            <button className="primary" type="submit">
              <Check size={17} />
              保存权限
            </button>
          </form>
        )}
      </div>

      <div className="database-grid">
        <div className="panel database-list">
          <div className="section-title">
            <h2>数据库文件</h2>
            <span>{databaseCount}</span>
          </div>
          {catalog.databases.map((database) => (
            <button
              key={database.path}
              className={`database-row ${selectedDatabasePath === database.path ? "active" : ""}`}
              onClick={() => onSelectDatabase(database.path)}
            >
              <span>
                <strong>{database.name}</strong>
                <small>{database.path}</small>
              </span>
              <small>{formatFileSize(database.size_bytes)}</small>
            </button>
          ))}
          {catalog.databases.length === 0 && <EmptyState text="项目目录下没有可读取的 SQLite 数据库文件。" />}
        </div>

        <div className="panel table-list">
          <div className="section-title">
            <h2>数据表</h2>
            <span>{selectedDatabase?.table_count ?? 0}</span>
          </div>
          {selectedDatabase?.error && <p className="muted">{selectedDatabase.error}</p>}
          {selectedDatabase?.tables.map((table) => (
            <button
              key={table.name}
              className={`table-row ${selectedTableName === table.name ? "active" : ""}`}
              onClick={() => onSelectTable(table.name)}
            >
              <span>
                <strong>{table.name}</strong>
                <small>{table.comment}</small>
              </span>
              <small>{table.row_count} 行</small>
            </button>
          ))}
          {selectedDatabase && selectedDatabase.tables.length === 0 && <EmptyState text="当前数据库没有可展示的数据表。" />}
        </div>

        <div className="panel table-detail">
          {selectedTable ? (
            <>
              <div className="section-title">
                <div>
                  <h2>{selectedTable.name}</h2>
                  <p className="muted">{selectedTable.comment}</p>
                </div>
                <span>{selectedTable.row_count} 行</span>
              </div>

              <div className="schema-table-wrap">
                <table className="schema-table">
                  <thead>
                    <tr>
                      <th>字段</th>
                      <th>中文注释</th>
                      <th>类型</th>
                      <th>约束</th>
                      <th>默认值</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedTable.columns.map((column) => (
                      <tr key={column.name}>
                        <td>
                          <code>{column.name}</code>
                        </td>
                        <td>{column.comment}</td>
                        <td>{column.type || "-"}</td>
                        <td>
                          {[
                            column.primary_key ? "主键" : null,
                            column.not_null ? "非空" : null,
                          ]
                            .filter(Boolean)
                            .join(" / ") || "-"}
                        </td>
                        <td>{column.default_value ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="section-title compact-title">
                <h3>随机示例数据</h3>
                <span>最多 5 条</span>
              </div>
              <SampleRowsTable table={selectedTable} />
            </>
          ) : (
            <EmptyState text="请选择一个数据表查看结构和示例数据。" />
          )}
        </div>
      </div>

      <DatabaseAiPanel currentUser={currentUser} />
    </section>
  );
}
