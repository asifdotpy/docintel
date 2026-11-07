"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useDropzone } from "react-dropzone";
import { getJob, uploadDocuments } from "@/lib/api";

type UploadResult = { document_ids: string[]; job_ids: string[] };

export default function Dropzone() {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string>("");
  const [result, setResult] = useState<UploadResult | null>(null);
  const [jobStatuses, setJobStatuses] = useState<Record<string, string>>({});
  const [jobErrors, setJobErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>("");

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((prev) => [...prev, ...accepted]);
    setError("");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  useEffect(() => {
    if (!result) return;
    let cancelled = false;

    async function poll() {
      const entries = await Promise.all(
        result!.job_ids.map(async (jobId, index) => {
          const documentId = result!.document_ids[index];
          try {
            const job = await getJob(jobId);
            return { documentId, status: job.status, error: job.error };
          } catch {
            return { documentId, status: "unreachable", error: "Could not read job status." };
          }
        }),
      );
      if (cancelled) return;

      setJobStatuses(Object.fromEntries(entries.map((entry) => [entry.documentId, entry.status])));
      setJobErrors(
        Object.fromEntries(
          entries.filter((entry) => entry.error).map((entry) => [entry.documentId, entry.error!]),
        ),
      );

      if (entries.some((entry) => entry.status === "queued" || entry.status === "running")) {
        setTimeout(poll, 1500);
      }
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [result]);

  async function handleUpload() {
    if (files.length === 0) return;
    setStatus("Uploading...");
    setError("");
    setJobStatuses({});
    setJobErrors({});
    try {
      const res = await uploadDocuments(files);
      setResult(res);
      setStatus("Uploaded");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
      setStatus("");
    }
  }

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer hover:border-blue-500"
      >
        <input {...getInputProps()} />
        {isDragActive ? <p>Drop files here...</p> : <p>Drag and drop files, or click to select</p>}
      </div>
      {files.length > 0 && (
        <ul className="text-sm">
          {files.map((f, i) => (
            <li key={i}>{f.name} ({Math.round(f.size / 1024)} KB)</li>
          ))}
        </ul>
      )}
      <button
        onClick={handleUpload}
        disabled={files.length === 0 || status === "Uploading..."}
        className="px-4 py-2 bg-blue-600 text-white rounded disabled:opacity-50"
      >
        Upload
      </button>
      {status && <p className="text-sm text-gray-600">{status}</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <div className="text-sm">
          <p className="font-medium mb-2">Processing status</p>
          <ul className="space-y-2">
            {result.document_ids.map((id, index) => (
              <li key={id} className="border p-3 rounded">
                <div className="flex items-center justify-between gap-2">
                  <span>{files[index]?.name ?? id}</span>
                  <span className="text-gray-600">{jobStatuses[id] ?? "queued"}</span>
                </div>
                {jobErrors[id] && <p className="text-red-600 text-xs mt-1">{jobErrors[id]}</p>}
                <Link href={`/documents/${id}`} className="text-blue-600 text-xs underline">
                  Inspect extracted data
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
