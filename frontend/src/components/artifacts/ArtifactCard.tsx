import { KeyboardEvent, MouseEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Share2 } from "lucide-react";
import type { Artifact } from "@/lib/api-contract";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ArtifactPreview } from "@/components/artifacts/ArtifactPreview";
import { ShareArtifactDialog } from "@/components/artifacts/ShareArtifactDialog";

export function ArtifactCard({ artifact }: { artifact: Artifact }) {
  const [shareOpen, setShareOpen] = useState(false);
  const navigate = useNavigate();

  function openArtifact() { navigate(`/artifact/${artifact.id}`); }
  function stopCardClick(event: MouseEvent) { event.stopPropagation(); }
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openArtifact(); }
  }

  return (
    <>
      <Card role="button" tabIndex={0} aria-label={`Open ${artifact.title}`} onClick={openArtifact} onKeyDown={handleKeyDown} className="min-w-0 cursor-pointer p-5 transition-transform hover:-translate-y-1 focus:outline-none focus:ring-2 focus:ring-slate-950">
        <ArtifactPreview type={artifact.type} url={artifact.thumbnailUrl ?? artifact.artifactUrl} />
        <div className="mt-6 min-w-0">
          <div className="flex min-w-0 items-start justify-between gap-3">
            <h3 className="line-clamp-2-safe text-2xl font-medium tracking-tight text-slate-950" title={artifact.title}>{artifact.title}</h3>
            <div className="shrink-0" onClick={stopCardClick}>
              <Button type="button" variant="outline" size="icon" aria-label={`Share ${artifact.title}`} onClick={() => setShareOpen(true)}>
                <Share2 className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <p className="mt-1 truncate-safe text-base text-slate-500" title={artifact.tags.join(" · ") || artifact.category}>{artifact.tags.join(" · ") || artifact.category}</p>
          <div className="mt-3 flex min-w-0 items-center justify-between gap-3">
            <Badge className="shrink-0">{artifact.commentCount} comments</Badge>
            <span className="truncate-safe text-sm text-slate-400" title={`Created by ${artifact.ownerName}`}>Created by {artifact.ownerName}</span>
          </div>
          {artifact.feedbackSummary && <p className="mt-3 line-clamp-2-safe text-sm text-emerald-700" title={artifact.feedbackSummary}>{artifact.feedbackSummary}</p>}
          {artifact.status === "processing" && <p className="mt-3 truncate-safe text-sm text-blue-600">Processing summary in background...</p>}
          {artifact.status === "failed" && <p className="mt-3 truncate-safe text-sm text-red-600" title={artifact.processingError ?? "Processing failed"}>Processing failed</p>}
        </div>
      </Card>
      <ShareArtifactDialog artifactId={artifact.id} open={shareOpen} onClose={() => setShareOpen(false)} />
    </>
  );
}
