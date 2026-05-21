import { useState } from "react";
import { useParams } from "react-router-dom";
import { Share2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ArtifactPreview } from "@/components/artifacts/ArtifactPreview";
import { ShareArtifactDialog } from "@/components/artifacts/ShareArtifactDialog";
import { ReviewPanel } from "@/components/review/ReviewPanel";
import { DocumentSummaryPanel } from "@/components/review/DocumentSummaryPanel";
import { useArtifact } from "@/hooks/use-artifacts";

export function ArtifactReviewPage() {
  const { artifactId = "" } = useParams();
  const [shareOpen, setShareOpen] = useState(false);
  const artifactQuery = useArtifact(artifactId);
  if (artifactQuery.isLoading) return <p className="text-slate-500">Loading artifact...</p>;
  if (artifactQuery.isError || !artifactQuery.data) return <p className="rounded-xl border bg-white p-4 text-red-600">Artifact not found.</p>;
  const artifact = artifactQuery.data;

  return (
    <div className="grid gap-8 lg:grid-cols-[1.8fr_1fr]">
      <Card className="min-w-0">
        <CardHeader className="flex min-w-0 flex-col justify-between gap-5 md:flex-row md:items-start">
          <div className="min-w-0">
            <div className="mb-3 flex min-w-0 flex-wrap items-center gap-2">
              <Badge>{artifact.type.toUpperCase()}</Badge>
              <Badge>{new Date(artifact.createdAt).toLocaleString()}</Badge>
              <Badge>{artifact.status}</Badge>
            </div>
            <h1 className="line-clamp-2-safe text-4xl font-bold tracking-tight text-slate-950 md:text-5xl" title={artifact.title}>{artifact.title}</h1>
            <p className="mt-2 truncate-safe text-lg text-slate-500" title={artifact.tags.join(" · ") || artifact.category}>{artifact.tags.join(" · ") || artifact.category}</p>
          </div>
          <Button size="icon" className="shrink-0 rounded-xl" aria-label="Share artifact" onClick={() => setShareOpen(true)}>
            <Share2 className="h-5 w-5" />
          </Button>
        </CardHeader>
        <CardContent>
          <ArtifactPreview type={artifact.type} url={artifact.artifactUrl} large />
          <DocumentSummaryPanel artifact={artifact} />
        </CardContent>
      </Card>
      <ReviewPanel artifact={artifact} />
      <ShareArtifactDialog artifactId={artifact.id} open={shareOpen} onClose={() => setShareOpen(false)} />
    </div>
  );
}
