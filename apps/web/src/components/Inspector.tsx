"use client";

import { useEffect, useState } from "react";
import { getDocument, correctDocument } from "@/lib/api";

export default function Inspector({ id }: { id: string }) {
  const [data, setData] = useState<Awaited<ReturnType<typeof getDocument>> | null>(null);
  const [error, setError] = useState<string>("");
  const [editing, setEditing] = useState(false);
  const [fields, setFields] = useState<Record<string, string>>({});

  async function load() {
    try {
      const d = await getDocument(id);
      setData(d);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function submitCorrection() {
    try {
      const parsed: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(fields)) {
        if (v !== "") parsed[k] = isNaN(Number(v)) ? v : Number(v);
      }
      await correctDocument(id, parsed);
      setEditing(false);
      setFields({});
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Correction failed");
    }
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!data) return <p>Loading...</p>;

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold">{data.document.filename}</h2>
      <p className="text-sm text-gray-600">Status: {data.document.status}</p>

      <div>
        <h3 className="font-medium">Extracted fields</h3>
        <pre className="bg-gray-100 p-3 rounded text-sm overflow-auto">
          {JSON.stringify(data.extraction, null, 2)}
        </pre>
      </div>

      <div>
        <h3 className="font-medium">Validation errors</h3>
        {data.validation_errors.length === 0 ? (
          <p className="text-sm text-green-600">None</p>
        ) : (
          <ul className="text-sm text-red-600 list-disc pl-5">
            {data.validation_errors.map((e) => (
              <li key={e.id}>{e.code}: {e.message} ({e.field})</li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <button
          onClick={() => setEditing((v) => !v)}
          className="px-3 py-1 bg-gray-200 rounded text-sm"
        >
          {editing ? "Cancel" : "Correct manually"}
        </button>
        {editing && (
          <div className="mt-2 space-y-2">
            <p className="text-xs text-gray-500">Enter field=value pairs (one per line not supported; use JSON keys)</p>
            <input
              className="border p-2 w-full text-sm"
              placeholder='e.g. total'
              onChange={(e) => setFields({ ...fields, total: e.target.value })}
            />
            <input
              className="border p-2 w-full text-sm"
              placeholder='supplier_name'
              onChange={(e) => setFields({ ...fields, supplier_name: e.target.value })}
            />
            <button
              onClick={submitCorrection}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm"
            >
              Save correction
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
