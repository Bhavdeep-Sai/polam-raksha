import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-base font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-brand-primary text-white hover:bg-brand-primary-hover",
        secondary: "bg-brand-secondary text-white hover:bg-brand-primary",
        accent: "bg-brand-accent text-brand-ink hover:brightness-95",
        outline:
          "border-2 border-brand-primary bg-white text-brand-primary hover:bg-brand-muted",
        ghost: "text-brand-ink hover:bg-brand-muted",
        destructive: "bg-red-700 text-white hover:bg-red-800",
      },
      size: {
        default: "min-h-11 px-4 py-2.5 text-base",
        lg: "min-h-13 px-6 py-3 text-lg",
        sm: "min-h-9 px-3 py-1.5 text-sm",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export function Button({
  className,
  variant,
  size,
  type = "button",
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  );
}
