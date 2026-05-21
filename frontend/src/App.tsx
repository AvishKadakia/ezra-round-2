import { useState } from "react";
import { Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { PublishArtifactDialog } from "@/components/artifacts/PublishArtifactDialog";
import { McpConfigDialog } from "@/components/artifacts/McpConfigDialog";
import { GalleryPage } from "@/pages/GalleryPage";
import { ArtifactReviewPage } from "@/pages/ArtifactReviewPage";
import { SharedArtifactPage } from "@/pages/SharedArtifactPage";
import { PlaceholderPage } from "@/pages/PlaceholderPage";
import type { ArtifactListParams } from "@/lib/api-contract";

export default function App() {
  const [searchValue, setSearchValue] = useState("");
  const [filters, setFilters] = useState<ArtifactListParams>({ type: "all", status: "all", sort: "newest" });
  const [publishOpen, setPublishOpen] = useState(false);
  const [mcpConfigOpen, setMcpConfigOpen] = useState(false);

  return (
    <>
      <Routes>
        <Route element={<AppShell searchValue={searchValue} onSearchChange={setSearchValue} onPublishClick={() => setPublishOpen(true)} />}>
          <Route index element={<GalleryPage searchValue={searchValue} filters={filters} onFiltersChange={setFilters} onOpenMcpConfig={() => setMcpConfigOpen(true)} />} />
          <Route path="artifact/:artifactId" element={<ArtifactReviewPage />} />
          <Route path="share/:artifactId" element={<SharedArtifactPage />} />
          <Route path="reviews" element={<PlaceholderPage title="Reviews" />} />
          <Route path="shared" element={<PlaceholderPage title="Shared artifacts" />} />
          <Route path="mcp" element={<PlaceholderPage title="MCP workspace" />} />
        </Route>
      </Routes>
      <PublishArtifactDialog open={publishOpen} onClose={() => setPublishOpen(false)} />
      <McpConfigDialog open={mcpConfigOpen} onClose={() => setMcpConfigOpen(false)} />
    </>
  );
}
