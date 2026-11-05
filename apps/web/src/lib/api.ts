const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function uploadDocuments(files: File[]): Promise<{ document_ids: string[]; job_ids: string[] }> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  const res = await fetch(`${API_URL}/api/documents/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function getDocument(id: string): Promise<{
  document: { id: string; filename: string; status: string };
  extraction: Record<string, unknown> | null;
  validation_errors: { id: number; code: string; field: string | null; message: string }[];
}> {
  const res = await fetch(`${API_URL}/api/documents/${id}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function correctDocument(id: string, fields: Record<string, unknown>): Promise<{ extraction: Record<string, unknown> }> {
  const res = await fetch(`${API_URL}/api/documents/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function searchDocuments(params: Record<string, string>): Promise<
  { id: string; filename: string; status: string; extraction: Record<string, unknown> | null; score: number | null }[]
> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${API_URL}/api/search?${qs}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
