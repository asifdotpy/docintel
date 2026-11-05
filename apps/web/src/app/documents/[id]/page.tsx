"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Inspector from "@/components/Inspector";
import CorrectionForm from "@/components/CorrectionForm";

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const [reloadKey, setReloadKey] = useState(0);

  return (
    <main className="max-w-2xl mx-auto p-8 space-y-4">
      <h1 className="text-2xl font-bold">Document Inspector</h1>
      <Inspector key={reloadKey} id={id} />
      <CorrectionForm id={id} onSaved={() => setReloadKey((k) => k + 1)} />
    </main>
  );
}
