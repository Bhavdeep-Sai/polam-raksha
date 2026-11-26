import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

import { Label } from "@/components/ui/label";

interface AccessibleFormFieldProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
}

export function AccessibleFormField({
  id,
  label,
  hint,
  error,
  required = false,
  children,
}: AccessibleFormFieldProps) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>
        {label}
        {required ? <span className="ml-1 text-red-700" aria-hidden="true">*</span> : null}
      </Label>
      {hint ? (
        <p id={`${id}-hint`} className="text-xs text-brand-ink-muted">
          {hint}
        </p>
      ) : null}
      {children}
      {error ? (
        <p
          id={`${id}-error`}
          role="alert"
          className="flex items-center gap-1.5 text-sm font-medium text-red-800"
        >
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

