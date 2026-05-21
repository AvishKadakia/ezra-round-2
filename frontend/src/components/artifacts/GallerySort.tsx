import type { ArtifactSort } from "@/lib/api-contract";

const sortOptions: { value: ArtifactSort; label: string }[] = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "recently_updated", label: "Recently updated" },
  { value: "recently_processed", label: "Recently processed" },
  { value: "most_comments", label: "Most comments" },
  { value: "least_comments", label: "Least comments" },
  { value: "title_az", label: "Title A-Z" },
  { value: "title_za", label: "Title Z-A" },
  { value: "status", label: "Status" },
  { value: "type", label: "Document type" },
];

export function GallerySort({ value, onChange }: { value: ArtifactSort; onChange: (sort: ArtifactSort) => void }) {
  return (
    <label className="flex items-center gap-2 text-sm text-slate-500">
      <span className="shrink-0 font-medium text-slate-600">Sort</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as ArtifactSort)}
        className="h-9 rounded-xl border bg-white px-3 text-sm font-medium text-slate-700 outline-none transition focus:ring-2 focus:ring-slate-950/20"
      >
        {sortOptions.map((option) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    </label>
  );
}
