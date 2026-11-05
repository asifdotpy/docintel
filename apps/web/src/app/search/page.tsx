"use client";

import { useState } from "react";
import { searchDocuments } from "@/lib/api";

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState("keyword");
  const [supplier, setSupplier] = useState("");
  const [results, setResults] = useState<Awaited<ReturnType<typeof searchDocuments>>>([]);
  const [error, setError] = useState("");

  async function run() {
    setError("");
    const params: Record<string, string> = { mode };
    if (q) params.q = q;
    if (supplier) params.supplier = supplier;
    try {
      const r = await searchDocuments(params);
      setResults(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    }
  }

  return (
    <main className="max-w-3xl mx-auto p-8 space-y-4">
      <h1 className="text-2xl font-bold">Search Documents</h1>
      <div className="flex gap-2">
        <input className="border p-2 flex-1" placeholder="query" value={q} onChange={(e) => setQ(e.target.value)} />
        <input className="border p-2" placeholder="supplier" value={supplier} onChange={(e) => setSupplier(e.target.value)} />
        <select className="border p-2" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="keyword">keyword</option>
          <option value="semantic">semantic</option>
          <option value="hybrid">hybrid</option>
        </select>
        <button onClick={run} className="px-4 py-2 bg-blue-600 text-white rounded">Search</button>
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <ul className="space-y-2">
        {results.map((r) => (
          <li key={r.id} className="border p-3 rounded">
            <a href={`/documents/${r.id}`} className="font-medium">{r.filename}</a>
            <span className="text-sm text-gray-500 ml-2">{r.status}</span>
            {r.score !== null && <span className="text-sm text-gray-500 ml-2">score: {r.score}</span>}
          </li>
        ))}
      </ul>
    </main>
  );
}
