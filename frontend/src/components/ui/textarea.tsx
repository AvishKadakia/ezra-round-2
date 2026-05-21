import * as React from "react";
import { cn } from "@/lib/utils";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;
export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea({ className, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      className={cn("min-h-10 w-full resize-none rounded-xl border bg-white px-4 py-3 text-sm outline-none transition-colors placeholder:text-slate-400 focus:ring-2 focus:ring-ring/20", className)}
      {...props}
    />
  );
});
