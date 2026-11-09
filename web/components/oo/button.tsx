import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background-color,border-color,color,box-shadow,transform] duration-150 ease-oo-out focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-oo-hema motion-safe:active:scale-[0.98] motion-reduce:transition-none [&_svg]:size-4 [&_svg]:shrink-0 disabled:pointer-events-none disabled:border-transparent disabled:bg-oo-line-soft disabled:text-oo-muted disabled:shadow-none aria-disabled:pointer-events-none aria-disabled:border-transparent aria-disabled:bg-oo-line-soft aria-disabled:text-oo-muted aria-disabled:shadow-none",
  {
    variants: {
      variant: {
        primary:
          "bg-oo-hema text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_1px_2px_rgb(27_22_38/0.2)] hover:bg-oo-hema-hover",
        secondary:
          "border border-oo-line bg-oo-surface text-oo-ink shadow-[0_1px_2px_rgb(27_22_38/0.06)] hover:border-oo-ink-3/40 hover:bg-oo-paper",
        ghost: "text-oo-ink-2 hover:bg-oo-line-soft hover:text-oo-ink disabled:bg-transparent aria-disabled:bg-transparent",
        danger:
          "bg-oo-status-failed-fg text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.12),0_1px_2px_rgb(27_22_38/0.2)] hover:bg-oo-status-failed-hover",
      },
      size: {
        sm: "h-8 px-3 text-[13px]",
        md: "h-9 px-3.5 text-[14px]",
        lg: "h-11 px-5 text-[15px]",
      },
      shape: {
        rounded: "rounded-md",
        pill: "rounded-full",
      },
    },
    defaultVariants: { variant: "primary", size: "md", shape: "rounded" },
  }
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, shape, asChild = false, loading = false, disabled, type, onClick, children, ...props }, ref) => {
    const classes = cn(buttonVariants({ variant, size, shape }), loading && "cursor-progress", className);

    if (asChild) {
      return (
        <Slot ref={ref} className={classes} aria-disabled={disabled || undefined} tabIndex={disabled ? -1 : undefined} onClick={onClick} {...props}>
          {children}
        </Slot>
      );
    }

    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={classes}
        disabled={disabled}
        aria-busy={loading || undefined}
        onClick={loading ? (e) => e.preventDefault() : onClick}
        {...props}
      >
        {loading ? <Loader2 className="animate-spin motion-reduce:animate-none" aria-hidden="true" /> : null}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
