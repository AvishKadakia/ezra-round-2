import { useState } from "react";
import type { ArtifactType } from "@/lib/api-contract";

const typeLabels: Record<ArtifactType, string> = { image: "IMG", pdf: "PDF" };

type ArtifactPreviewProps = { type: ArtifactType; url?: string | null; large?: boolean };

function pdfPreviewUrl(url: string) {
  return `${url}#toolbar=0&navpanes=0&scrollbar=0&page=1&view=FitH`;
}

function PreviewFallback({ type, url, large, message }: { type: ArtifactType; url?: string | null; large: boolean; message?: string }) {
  return (
    <div className={large ? "flex min-h-72 items-center justify-between rounded-2xl border bg-slate-50 p-10" : "rounded-2xl border bg-slate-50 p-6"}>
      <div className={large ? "min-w-0 w-2/3" : "min-w-0 w-full"}>
        <div className="mb-6 h-4 w-56 max-w-full rounded-full bg-slate-950" />
        <div className="mb-4 h-4 w-full max-w-md rounded-full bg-slate-300" />
        <div className="mb-3 h-4 w-4/5 max-w-sm rounded-full bg-slate-200" />
        {message ? <p className="mb-4 line-clamp-2-safe text-sm text-slate-500">{message}</p> : null}
        {large && url ? <a href={url} target="_blank" rel="noreferrer" className="inline-flex rounded-xl bg-slate-950 px-8 py-3 text-white">Open file</a> : null}
      </div>
      {large ? (
        <div className="hidden w-56 rounded-2xl border bg-white p-7 md:block">
          <div className="mb-4 h-3 w-36 rounded-full bg-slate-300" /><div className="mb-3 h-3 w-28 rounded-full bg-slate-200" /><div className="mb-3 h-3 w-24 rounded-full bg-slate-200" /><div className="h-3 w-20 rounded-full bg-slate-200" />
        </div>
      ) : (
        <div className="mt-5 flex items-end justify-between">
          <div className="space-y-3"><div className="h-3 w-48 rounded-full bg-slate-300" /><div className="h-3 w-36 rounded-full bg-slate-200" /><div className="h-3 w-28 rounded-full bg-slate-200" /></div>
          <span className="rounded-full border bg-white px-3 py-1 text-sm font-medium text-slate-700">{typeLabels[type]}</span>
        </div>
      )}
    </div>
  );
}

export function ArtifactPreview({ type, url, large = false }: ArtifactPreviewProps) {
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    return <PreviewFallback type={type} url={url} large={large} message={failed ? "Preview could not be loaded. Open the artifact to view the file." : undefined} />;
  }

  if (type === "image") {
    return (
      <div className="overflow-hidden rounded-2xl border bg-slate-50">
        <img
          src={url}
          alt="Artifact preview"
          loading="lazy"
          onError={() => setFailed(true)}
          className={large ? "h-80 w-full object-contain" : "h-32 w-full object-cover"}
        />
      </div>
    );
  }

  if (type === "pdf") {
    return (
      <div className="relative overflow-hidden rounded-2xl border bg-slate-50">
        <object
          data={pdfPreviewUrl(url)}
          type="application/pdf"
          title="PDF artifact preview"
          className={large ? "h-96 w-full bg-white" : "pointer-events-none h-32 w-full bg-white"}
        >
          <PreviewFallback type={type} url={url} large={large} message="PDF preview is not available in this browser. Open the artifact to view the file." />
        </object>
        {!large && <span className="absolute right-3 top-3 rounded-full border bg-white/90 px-3 py-1 text-sm font-medium text-slate-700">PDF</span>}
      </div>
    );
  }

  return <PreviewFallback type={type} url={url} large={large} />;
}
