import Dropzone from "@/components/Dropzone";

export default function Home() {
  return (
    <main className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-4">DocIntel — Document Upload</h1>
      <Dropzone />
    </main>
  );
}
