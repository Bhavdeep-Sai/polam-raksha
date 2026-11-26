import { forwardRef, type InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={cn(
          "min-h-11 w-full rounded-lg border-2 border-brand-border bg-white px-3.5 py-2 text-base text-brand-ink placeholder:text-brand-ink-muted focus:border-brand-primary focus:outline-none disabled:cursor-not-allowed disabled:bg-brand-muted",
          className,
        )}
        {...props}
      />
    );
  },
);
Input.displayName = "Input";

