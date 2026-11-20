import { Loader2 } from "lucide-react";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/utils/cn";

type Variant = "primary" | "secondary" | "outline" | "ghost" | "danger" | "inverse" | "inverse-ghost";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  fullWidth?: boolean;
}

const variants: Record<Variant, string> = {
  primary: "bg-brand-500 text-white hover:bg-brand-600 active:bg-brand-700 shadow-sm disabled:bg-brand-300",
  secondary: "bg-brand-100 text-brand-700 hover:bg-brand-200 active:bg-brand-300",
  outline: "border border-line bg-white text-ink hover:border-brand-300 hover:bg-brand-50",
  ghost: "text-brand-600 hover:bg-brand-50",
  danger: "bg-rose-600 text-white hover:bg-rose-700 disabled:bg-rose-300",
  // for use on dark purple panels
  inverse: "bg-white text-brand-700 hover:bg-brand-50 shadow-sm",
  "inverse-ghost": "text-white hover:bg-white/10",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-12 px-6 text-base gap-2",
};

const buttonClasses = (variant: Variant = "primary", size: Size = "md", extra?: string) =>
  cn(
    "inline-flex items-center justify-center rounded-xl font-semibold transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70",
    variants[variant],
    sizes[size],
    extra,
  );

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, leftIcon, rightIcon, fullWidth, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(buttonClasses(variant, size), fullWidth && "w-full", className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : leftIcon}
      {children}
      {!loading && rightIcon}
    </button>
  );
});

export function LinkButton({
  to,
  variant = "primary",
  size = "md",
  className,
  children,
  leftIcon,
}: {
  to: string;
  variant?: Variant;
  size?: Size;
  className?: string;
  children: ReactNode;
  leftIcon?: ReactNode;
}) {
  return (
    <Link to={to} className={buttonClasses(variant, size, className)}>
      {leftIcon}
      {children}
    </Link>
  );
}
