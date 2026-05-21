import * as React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

type DialogProps = {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  maxWidth?: string;

  /**
   * Defaults to true so modals close when the user clicks the dimmed backdrop.
   * Set to false only for destructive confirmations or flows that must not be dismissed.
   */
  closeOnOverlayClick?: boolean;
};

export function Dialog({
  open,
  title,
  children,
  onClose,
  maxWidth = "max-w-lg",
  closeOnOverlayClick = true,
}: DialogProps) {
  React.useEffect(() => {
    if (!open) return;

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [open, onClose]);

  if (!open) return null;

  function handleOverlayMouseDown(event: React.MouseEvent<HTMLDivElement>) {
    if (!closeOnOverlayClick) return;

    // Only close when clicking the backdrop, not when clicking inside the modal.
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-950/40 p-4 sm:items-center sm:p-6"
      onMouseDown={handleOverlayMouseDown}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className={`my-auto flex max-h-[calc(100vh-2rem)] w-full min-w-0 ${maxWidth} flex-col overflow-hidden rounded-2xl border bg-white shadow-soft`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-center justify-between gap-4 border-b px-6 py-5">
          <h2 id="dialog-title" className="truncate text-xl font-semibold text-slate-950">
            {title}
          </h2>

          <Button variant="ghost" size="icon" aria-label="Close dialog" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {children}
        </div>
      </section>
    </div>
  );
}