import { useState } from "react";
import type { Artifact } from "@/lib/api-contract";
import { Button } from "@/components/ui/button";
import { useRefreshDocumentSummary } from "@/hooks/use-artifacts";

export function DocumentSummaryPanel({ artifact }: { artifact: Artifact }) {
  const [mode, setMode] = useState<"overall" | "pages">("overall");
  const refresh = useRefreshDocumentSummary(artifact.id);
  const hasPages = Boolean(artifact.pageSummaries?.length);

  return (
    <section className="mt-8 rounded-2xl border bg-slate-50 p-6">
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3">
        <h2 className="truncate-safe text-2xl font-medium text-slate-950">Document summary</h2>
        <div className="flex shrink-0 gap-2">
          <Button type="button" size="sm" variant={mode === "overall" ? "default" : "outline"} onClick={() => setMode("overall")}>Overall</Button>
          <Button type="button" size="sm" variant={mode === "pages" ? "default" : "outline"} disabled={!hasPages} onClick={() => setMode("pages")}>Pages</Button>
          <Button type="button" size="sm" variant="outline" disabled={refresh.isPending || artifact.status === "processing"} onClick={() => refresh.mutate()}>{refresh.isPending ? "Queued..." : "Refresh"}</Button>
        </div>
      </div>

      {artifact.status === "processing" && <p className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-3 text-sm text-blue-700">Processing in the background. The page will refresh automatically when the worker finishes.</p>}
      {artifact.status === "failed" && <p className="mt-4 rounded-xl border border-red-100 bg-red-50 p-3 text-sm text-red-700">Processing failed: {artifact.processingError || "Unknown error"}</p>}

      {mode === "overall" ? (
        <p className="mt-4 leading-7 text-slate-700">{artifact.documentSummary || "No document summary has been generated yet."}</p>
      ) : (
        <div className="mt-4 space-y-4">
          {artifact.pageSummaries?.map((page) => (
            <div key={page.pageNumber} className="min-w-0 rounded-xl border bg-white p-4">
              <p className="truncate-safe text-sm font-semibold text-slate-950">Page {page.pageNumber}</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">{page.summary}</p>
            </div>
          ))}
        </div>
      )}
      {refresh.isError && <p className="mt-3 text-xs text-red-600">Could not queue the summary refresh.</p>}
    </section>
  );
}
