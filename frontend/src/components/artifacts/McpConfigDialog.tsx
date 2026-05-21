import { Copy } from "lucide-react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { useMcpConfig } from "@/hooks/use-artifacts";

function CodeBlock({ label, value }: { label: string; value: string }) {
  async function copy() {
    await navigator.clipboard.writeText(value).catch(() => undefined);
  }

  return (
    <div className="mt-4 min-w-0">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="truncate-safe text-sm font-semibold text-slate-700">{label}</p>
        <Button type="button" variant="outline" size="sm" className="gap-2" onClick={copy}>
          <Copy className="h-4 w-4" /> Copy
        </Button>
      </div>
      <pre className="max-h-64 overflow-auto rounded-2xl bg-slate-950 p-5 text-sm text-slate-100">
        <code>{value}</code>
      </pre>
    </div>
  );
}

export function McpConfigDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const configQuery = useMcpConfig();
  const config = configQuery.data;
  const claudePayload = config ? JSON.stringify(config.claude.messagesApiExample, null, 2) : "Loading...";
  const codexPayload = config?.codex.configTomlExample ?? "Loading...";

  return (
    <Dialog open={open} title="MCP configuration" onClose={onClose} maxWidth="max-w-3xl">
      <p className="text-sm leading-6 text-slate-500">
        Artifact Hub now exposes a remote Streamable HTTP MCP server. Paste the URL directly into clients that support remote MCP servers; no local npx bridge or project-specific setup is required.
      </p>

      {configQuery.isError && (
        <p className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Could not load MCP configuration. Check that the backend is running.
        </p>
      )}

      <div className="mt-5 rounded-2xl border bg-slate-50 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Remote MCP URL</p>
        <p className="mt-2 truncate-safe text-base font-semibold text-slate-950" title={config?.remoteMcpUrl}>{config?.remoteMcpUrl ?? "Loading..."}</p>
      </div>

      <CodeBlock label="Claude / Messages API MCP server payload" value={claudePayload} />
      <CodeBlock label="Codex config.toml snippet" value={codexPayload} />

      {config?.capabilities?.length ? (
        <div className="mt-5 rounded-2xl border bg-white p-4">
          <p className="text-sm font-semibold text-slate-950">Agent capabilities</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {config.capabilities.map((capability) => (
              <span key={capability} className="rounded-full border bg-slate-50 px-3 py-1 text-xs text-slate-600">{capability}</span>
            ))}
          </div>
        </div>
      ) : null}
    </Dialog>
  );
}
