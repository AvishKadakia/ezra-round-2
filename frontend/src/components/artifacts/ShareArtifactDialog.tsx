import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { useCreateShareLink } from "@/hooks/use-artifacts";

const EXPIRY_OPTIONS = [24, 36, 72] as const;
type ExpiryHours = (typeof EXPIRY_OPTIONS)[number];

export function ShareArtifactDialog({ artifactId, open, onClose }: { artifactId: string; open: boolean; onClose: () => void }) {
  const [shareUrl, setShareUrl] = useState("");
  const [selectedHours, setSelectedHours] = useState<ExpiryHours>(72);
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const createShareLink = useCreateShareLink(artifactId);

  async function handleCreateLink() {
    const link = await createShareLink.mutateAsync({ access: "anyone_with_link", expiresInHours: selectedHours });
    setShareUrl(link.url);
    setCopyStatus("idle");
  }

  async function handleCopyLink() {
    if (!shareUrl) return;
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopyStatus("copied");
    } catch {
      setCopyStatus("failed");
    }
  }

  return (
    <Dialog open={open} title="Share artifact" onClose={onClose}>
      <p className="text-sm text-slate-500">Choose how long this shared link should stay accessible.</p>
      <div className="mt-5">
        <label className="mb-2 block text-sm font-medium text-slate-600">Link duration</label>
        <div className="grid grid-cols-3 gap-2">
          {EXPIRY_OPTIONS.map((hours) => (
            <Button key={hours} type="button" variant={selectedHours === hours ? "default" : "outline"} className={cn("rounded-xl", selectedHours === hours && "shadow-sm")} onClick={() => setSelectedHours(hours)}>
              {hours}h
            </Button>
          ))}
        </div>
      </div>
      <div className="mt-5">
        <Button disabled={createShareLink.isPending} onClick={handleCreateLink} className="w-full">
          {createShareLink.isPending ? "Generating..." : `Generate ${selectedHours}h link`}
        </Button>
      </div>
      {createShareLink.isError && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">Could not create a share link.</p>}
      {shareUrl && (
        <div className="mt-5 space-y-3">
          <label className="block text-sm font-medium text-slate-600">Share URL</label>
          <div className="flex gap-2">
            <Input readOnly value={shareUrl} onFocus={(event) => event.currentTarget.select()} />
            <Button type="button" variant="outline" className="gap-2" onClick={handleCopyLink}>
              {copyStatus === "copied" ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              {copyStatus === "copied" ? "Copied" : "Copy"}
            </Button>
          </div>
          {copyStatus === "failed" && <p className="text-xs text-amber-700">Browser clipboard access was blocked. Select and copy manually.</p>}
        </div>
      )}
    </Dialog>
  );
}
