"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { uploadDocuments } from "@/lib/api";

export default function Dropzone() {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string>("");
  const [result, setResult] = useState<{ document_ids: string[]; job_ids: string[] } | null>(null);
  const [error, setError] = useState<string>("");

  const onDrop = useCallback((accepted: File[]) => {
    setFiles((prev) => [...prev, ...accepted]);
    setError("");
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ onDrop });

  async function handleUpload() {
    if (files.length === 0) return;
    setStatus("Uploading...");
    setError("");
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
          <p>Document IDs:</p>
          <ul>{result.document_ids.map((id) => <li key={id}>{id}</li>)}</ul>
          <p>Job IDs:</p>
          <ul>{result.job_ids.map((id) => <li key={id}>{id}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
