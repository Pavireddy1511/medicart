import { forwardRef, useId, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

import { inputClasses } from "@/components/ui/styles";
import { cn } from "@/utils/cn";

interface FieldProps {
  label?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  className?: string;
  children: (id: string, describedBy: string | undefined) => ReactNode;
}

export function Field({ label, hint, error, required, className, children }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-ink">
          {label}
          {required && <span className="ml-0.5 text-rose-600">*</span>}
        </label>
      )}
      {children(id, [hintId, errorId].filter(Boolean).join(" ") || undefined)}
      {error ? (
        <p id={errorId} className="text-xs font-medium text-rose-600">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  leftIcon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, required, className, leftIcon, ...rest },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(id, describedBy) => (
        <div className="relative">
          {leftIcon && (
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-muted">{leftIcon}</span>
          )}
          <input
            ref={ref}
            id={id}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            className={inputClasses(Boolean(error), leftIcon ? "pl-9" : undefined)}
            {...rest}
          />
        </div>
      )}
    </Field>
  );
});

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, required, className, ...rest },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(id, describedBy) => (
        <textarea
          ref={ref}
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={cn(inputClasses(Boolean(error)), "h-auto min-h-[88px] py-2 leading-relaxed")}
          {...rest}
        />
      )}
    </Field>
  );
});

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
  error?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, error, required, className, options, placeholder, ...rest },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={required} className={className}>
      {(id, describedBy) => (
        <select
          ref={ref}
          id={id}
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy}
          className={cn(inputClasses(Boolean(error)), "appearance-none bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2216%22 height=%2216%22 viewBox=%220 0 24 24%22 fill=%22none%22 stroke=%22%236b6480%22 stroke-width=%222%22><path d=%22m6 9 6 6 6-6%22/></svg>')] bg-[length:16px] bg-[right_0.75rem_center] bg-no-repeat pr-9")}
          {...rest}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
});

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  description?: string;
}

export function Checkbox({ label, description, className, ...rest }: CheckboxProps) {
  const id = useId();
  return (
    <label htmlFor={id} className={cn("flex cursor-pointer items-start gap-3", className)}>
      <input
        id={id}
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-line text-brand-500 accent-brand-500 focus:ring-brand-300"
        {...rest}
      />
      <span className="text-sm">
        <span className="font-medium text-ink">{label}</span>
        {description && <span className="block text-muted">{description}</span>}
      </span>
    </label>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:opacity-50",
        checked ? "bg-brand-500" : "bg-brand-200",
      )}
    >
      <span
        className={cn(
          "inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform",
          checked ? "translate-x-5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}
