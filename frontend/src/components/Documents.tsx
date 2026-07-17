import { useEffect, useState, type ChangeEvent } from "react";
import { listDocuments, uploadDocument, login, loggedIn } from "../api";

interface Doc {
  id: string;
  filename: string;
  corpus_label: string;
  chunks: number;
}

export function Documents() {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [label, setLabel] = useState("clean");

  async function refresh() {
    setDocs(await listDocuments());
  }
  useEffect(() => {
    refresh();
  }, []);

  async function onUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!loggedIn()) await login("admin@ragguard.local", "ragguard-admin").catch(() => {});
    await uploadDocument(file, label).catch((err) => alert(err.message));
    refresh();
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-2 mb-4">
        <select
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          className="bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-sm"
        >
          <option value="clean">clean</option>
          <option value="poisoned">poisoned</option>
        </select>
        <label className="px-3 py-1.5 bg-blue-600 rounded-md text-sm font-semibold cursor-pointer">
          Upload .md/.txt
          <input type="file" accept=".md,.txt" className="hidden" onChange={onUpload} />
        </label>
      </div>
      <table className="w-full text-sm">
        <thead className="text-slate-400 text-left">
          <tr>
            <th className="py-1">filename</th>
            <th>label</th>
            <th>chunks</th>
          </tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id} className="border-t border-slate-800">
              <td className="py-1">{d.filename}</td>
              <td>
                <span
                  className={`px-1.5 rounded text-xs ${
                    d.corpus_label === "poisoned"
                      ? "bg-red-600/30 text-red-300"
                      : "bg-slate-700 text-slate-300"
                  }`}
                >
                  {d.corpus_label}
                </span>
              </td>
              <td>{d.chunks}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
