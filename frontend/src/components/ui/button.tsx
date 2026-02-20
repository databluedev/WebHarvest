import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-sm font-semibold tracking-[-0.01em] ring-offset-background transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/30 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 active:scale-[0.97]",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground rounded-xl shadow-md shadow-primary/10 hover:bg-primary/90 hover:shadow-lg hover:shadow-primary/15",
        destructive:
          "bg-destructive text-destructive-foreground rounded-xl shadow-md shadow-destructive/10 hover:bg-destructive/90",
        outline:
          "border border-border/50 bg-background/30 backdrop-blur-sm rounded-xl hover:bg-foreground/[0.04] hover:border-border/80",
        secondary:
          "bg-secondary text-secondary-foreground rounded-xl hover:bg-secondary/80",
        ghost:
          "rounded-xl hover:bg-foreground/[0.04] hover:text-foreground",
        link:
          "text-primary underline-offset-4 hover:underline",
        glow:
          "bg-primary text-primary-foreground rounded-xl shadow-[0_0_24px_-6px_hsla(var(--primary),0.35)] hover:shadow-[0_0_32px_-4px_hsla(var(--primary),0.45)] hover:bg-primary/90",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-11 px-6 text-[15px]",
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
