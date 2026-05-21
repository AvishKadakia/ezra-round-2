import { Button } from "@/components/ui/button";

export function McpBanner({ onOpenConfig }: { onOpenConfig: () => void }) {
  return (
    <div className="mb-12 flex min-w-0 items-center justify-between gap-4 rounded-2xl bg-slate-950 px-7 py-3 text-white shadow-soft">
      <p className="truncate-safe text-lg tracking-wide">
        <span className="font-semibold">MCP ready</span>{" "}
        <span className="text-slate-300">Remote MCP tools for publishing, feedback, summaries and sharing.</span>
      </p>
      <Button variant="outline" className="shrink-0 rounded-xl border-white bg-white px-7 text-slate-950 hover:bg-slate-100" onClick={onOpenConfig}>
        MCP Config
      </Button>
    </div>
  );
}
