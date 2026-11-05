import Dropzone from "@/components/Dropzone";

export default function UploadPage() {
  return (
    <main className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">Upload Documents</h1>
      <Dropzone />
    </main>
  );
}
