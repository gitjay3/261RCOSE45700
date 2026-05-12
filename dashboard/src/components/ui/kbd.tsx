import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

// data-slot="kbd"는 tooltip.tsx selector(`has-data-[slot=kbd]:pr-1.5`,
// `**:data-[slot=kbd]:rounded-sm` 등)와 연동되어 tooltip 안에서도 자동 동작.
const kbdVariants = cva(
  "font-mono inline-flex items-center justify-center rounded text-xs",
  {
    variants: {
      variant: {
        default: "bg-muted text-foreground",
        inverse: "bg-primary-foreground/15",
        outline: "bg-bg-sunk border border-border-1 text-foreground",
      },
      size: {
        xs: "px-1",
        sm: "px-1.5 py-0.5",
        md: "min-w-[24px] px-1.5 py-0.5",
      },
    },
    defaultVariants: { variant: "default", size: "sm" },
  }
)

type KbdProps = React.ComponentProps<"kbd"> & VariantProps<typeof kbdVariants>

function Kbd({ className, variant, size, ...props }: KbdProps) {
  return (
    <kbd
      data-slot="kbd"
      className={cn(kbdVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { Kbd, kbdVariants }
