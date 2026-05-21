import type { Metrics } from "@/lib/api-contract";

function StatCard({ value, label }: { value: number; label: string }) {
  return (
    <div className="flex min-w-52 max-w-full items-center rounded-2xl border bg-white px-7 py-5 shadow-sm">
      <span className="shrink-0 text-4xl font-light tracking-tight text-slate-950">{value}</span>
      <span className="ml-2 truncate-safe text-lg font-medium text-slate-500" title={label}>{label}</span>
    </div>
  );
}

export function MetricsCards({ metrics }: { metrics?: Metrics }) {
  return (
    <div className="mt-8 flex flex-wrap gap-5">
      <StatCard value={metrics?.totalDocuments ?? 0} label="Total documents uploaded" />
      <StatCard value={metrics?.totalComments ?? 0} label="Total comments" />
    </div>
  );
}
