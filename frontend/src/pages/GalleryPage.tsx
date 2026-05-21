import { ArtifactCard } from "@/components/artifacts/ArtifactCard";
import { GalleryFilters } from "@/components/artifacts/GalleryFilters";
import { GallerySort } from "@/components/artifacts/GallerySort";
import { McpBanner } from "@/components/artifacts/McpBanner";
import { MetricsCards } from "@/components/artifacts/MetricsCards";
import { useArtifacts, useMetrics } from "@/hooks/use-artifacts";
import type { ArtifactListParams } from "@/lib/api-contract";

type GalleryPageProps = {
  searchValue: string;
  filters: ArtifactListParams;
  onFiltersChange: (filters: ArtifactListParams) => void;
  onOpenMcpConfig: () => void;
};

export function GalleryPage({ searchValue, filters, onFiltersChange, onOpenMcpConfig }: GalleryPageProps) {
  const artifactsQuery = useArtifacts({ ...filters, q: searchValue });
  const metricsQuery = useMetrics();

  return (
    <section>
      <McpBanner onOpenConfig={onOpenMcpConfig} />
      <div className="max-w-4xl">
        <h1 className="text-6xl font-bold tracking-tight text-slate-950 md:text-7xl">Gallery-first catalog</h1>
        <p className="mt-4 text-xl text-slate-600">A lightweight browsing experience for teams to find, open, and review generated artifacts quickly.</p>
      </div>
      <MetricsCards metrics={metricsQuery.data} />
      <div className="mt-8 flex flex-wrap items-center justify-between gap-4">
        <GalleryFilters active={filters} onChange={onFiltersChange} />
        <GallerySort value={filters.sort ?? "newest"} onChange={(sort) => onFiltersChange({ ...filters, sort })} />
      </div>
      {artifactsQuery.isLoading && <p className="mt-10 text-slate-500">Loading artifacts...</p>}
      {artifactsQuery.isError && <p className="mt-10 rounded-xl border bg-white p-4 text-red-600">Could not load artifacts. Check FastAPI and VITE_API_BASE_URL.</p>}
      <div className="mt-12 grid gap-8 md:grid-cols-2 xl:grid-cols-3">
        {artifactsQuery.data?.map((artifact) => <ArtifactCard key={artifact.id} artifact={artifact} />)}
      </div>
      {artifactsQuery.data?.length === 0 && <div className="mt-12 rounded-2xl border bg-white p-10 text-center text-slate-500">No artifacts yet, or nothing matched your search. Publish files to create the first cards.</div>}
    </section>
  );
}
