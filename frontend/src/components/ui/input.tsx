import * as React from "react";
import { cn } from "@/lib/utils";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export const Input = React.forwardRef<HTMLInputElement, InputProps>(function Input({ className, ...props }, ref) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-xl border bg-white px-4 text-sm outline-none transition-all duration-300",
        "placeholder:text-slate-400 focus:ring-2 focus:ring-ring/20",
        className,
      )}
      {...props}
    />
  );
});
