import type { ArtifactListParams, ArtifactType } from "@/lib/api-contract";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type FilterOption = { label: string; type?: ArtifactType | "all"; status?: ArtifactListParams["status"] };
const filterOptions: FilterOption[] = [
  { label: "All", type: "all", status: "all" },
  { label: "Images", type: "image" },
  { label: "PDFs", type: "pdf" },
  { label: "Processing", status: "processing" },
  // { label: "Ready", status: "ready" },
  // { label: "Failed", status: "failed" },
];

export function GalleryFilters({ active, onChange }: { active: ArtifactListParams; onChange: (next: ArtifactListParams) => void }) {
  return (
    <div className="flex flex-wrap gap-2">
      {filterOptions.map((option) => {
        const isActive = option.label === "All" ? (active.type ?? "all") === "all" && (active.status ?? "all") === "all" : (option.type && active.type === option.type) || (option.status && active.status === option.status);
        return (
          <Button key={option.label} variant={isActive ? "default" : "outline"} size="sm" className={cn("rounded-xl px-5", !isActive && "text-slate-600")} onClick={() => onChange(option.label === "All" ? { ...active, type: "all", status: "all" } : { ...active, type: option.type ?? "all", status: option.status ?? "all" })}>
            {option.label}
          </Button>
        );
      })}
    </div>
  );
}
