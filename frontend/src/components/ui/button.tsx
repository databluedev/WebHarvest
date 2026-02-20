import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground rounded-md hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground rounded-md hover:bg-destructive/90",
        outline:
          "border border-border bg-background rounded-md hover:bg-muted hover:text-foreground",
        secondary:
          "bg-secondary text-secondary-foreground rounded-md hover:bg-secondary/80",
        ghost:
          "rounded-md hover:bg-muted hover:text-foreground",
        link:
          "text-primary underline-offset-4 hover:underline",
        glow:
          "bg-primary text-primary-foreground rounded-md shadow-[0_0_20px_-6px_hsla(var(--primary),0.3)] hover:shadow-[0_0_28px_-4px_hsla(var(--primary),0.4)] hover:bg-primary/90",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-10 px-5",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
