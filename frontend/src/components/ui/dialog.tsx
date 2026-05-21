import * as React from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";

type DialogProps = {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  maxWidth?: string;
};

export function Dialog({ open, title, children, onClose, maxWidth = "max-w-lg" }: DialogProps) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 p-4">
      <div className={`w-full ${maxWidth} rounded-2xl border bg-white p-6 shadow-soft`}>
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-slate-950">{title}</h2>
          <Button variant="ghost" size="icon" aria-label="Close dialog" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        {children}
      </div>
    </div>
  );
}
