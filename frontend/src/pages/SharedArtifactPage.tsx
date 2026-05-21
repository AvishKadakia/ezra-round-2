import { Link, useParams, useSearchParams } from "react-router-dom";
import { ExternalLink } from "lucide-react";
import { ArtifactPreview } from "@/components/artifacts/ArtifactPreview";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSharedArtifact } from "@/hooks/use-artifacts";

export function SharedArtifactPage() {
  const { artifactId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token") ?? undefined;
  const artifactQuery = useSharedArtifact(artifactId, token);

  if (artifactQuery.isLoading) return <p className="text-slate-500">Opening shared artifact...</p>;
  if (artifactQuery.isError || !artifactQuery.data) {
    return (
      <Card><CardContent className="p-10"><h1 className="text-3xl font-bold text-slate-950">Shared link unavailable</h1><p className="mt-3 text-slate-500">This link may be expired or invalid.</p></CardContent></Card>
    );
  }
  const artifact = artifactQuery.data;
  return (
    <div className="mx-auto max-w-5xl">
      <Card className="min-w-0">
        <CardHeader className="flex min-w-0 flex-col justify-between gap-5 md:flex-row md:items-start">
          <div className="min-w-0">
            <div className="mb-3 flex min-w-0 flex-wrap items-center gap-2"><Badge>Shared artifact</Badge><Badge>{artifact.type.toUpperCase()}</Badge><Badge>{new Date(artifact.createdAt).toLocaleString()}</Badge><Badge>{artifact.status}</Badge></div>
            <h1 className="line-clamp-2-safe text-4xl font-bold tracking-tight text-slate-950 md:text-5xl" title={artifact.title}>{artifact.title}</h1>
            <p className="mt-2 line-clamp-2-safe max-w-2xl text-lg text-slate-500" title={artifact.description}>{artifact.description}</p>
          </div>
          <Link to={`/artifact/${artifact.id}`} className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-primary px-7 text-base font-medium text-primary-foreground transition-colors hover:bg-primary/90">
            Open review workspace <ExternalLink className="h-4 w-4" />
          </Link>
        </CardHeader>
        <CardContent>
          <ArtifactPreview type={artifact.type} url={artifact.artifactUrl} large />
          {artifact.documentSummary && <section className="mt-8 rounded-2xl border bg-slate-50 p-6"><h2 className="truncate-safe text-xl font-medium text-slate-950">Summary</h2><p className="mt-3 leading-7 text-slate-700">{artifact.documentSummary}</p></section>}
        </CardContent>
      </Card>
    </div>
  );
}
