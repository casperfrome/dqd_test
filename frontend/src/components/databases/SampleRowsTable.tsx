import type { DatabaseTable } from "../../api/types";
import { formatCellValue } from "../../utils/helpers";
import { EmptyState } from "../ui/EmptyState";

export function SampleRowsTable({ table }: { table: DatabaseTable }) {
  const columnNames = table.columns.map((column) => column.name);
  if (table.sample_rows.length === 0) {
    return <EmptyState text="当前表暂无示例数据。" />;
  }
  return (
    <div className="sample-table-wrap">
      <table className="sample-table">
        <thead>
          <tr>
            {columnNames.map((columnName) => (
              <th key={columnName}>{columnName}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.sample_rows.map((row, index) => (
            <tr key={index}>
              {columnNames.map((columnName) => (
                <td key={columnName}>{formatCellValue(row[columnName])}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
