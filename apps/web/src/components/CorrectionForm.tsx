"use client";

import { useState } from "react";
import { correctDocument } from "@/lib/api";

export default function CorrectionForm({ id, onSaved }: { id: string; onSaved: () => void }) {
  const [field, setField] = useState("");
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    const parsed: Record<string, unknown> = {};
    parsed[field] = isNaN(Number(value)) ? value : Number(value);
    try {
      await correctDocument(id, parsed);
      setField("");
      setValue("");
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <input className="border p-2 w-full text-sm" placeholder="field name" value={field} onChange={(e) => setField(e.target.value)} />
      <input className="border p-2 w-full text-sm" placeholder="value" value={value} onChange={(e) => setValue(e.target.value)} />
      <button type="submit" className="px-3 py-1 bg-blue-600 text-white rounded text-sm">Save</button>
      {error && <p className="text-sm text-red-600">{error}</p>}
    </form>
  );
}
