"use client";

import * as Menu from "@radix-ui/react-dropdown-menu";
import * as React from "react";

import { cn } from "@/lib/utils";

export const DropdownMenu = Menu.Root;
export const DropdownTrigger = Menu.Trigger;

export function DropdownContent({ className, ...props }: React.ComponentProps<typeof Menu.Content>) {
  return (
    <Menu.Portal>
      <Menu.Content
        align="end"
        sideOffset={8}
        className={cn("z-50 min-w-[220px] rounded-lg border bg-white p-1.5 shadow-pop", className)}
        {...props}
      />
    </Menu.Portal>
  );
}

export function DropdownItem({ className, ...props }: React.ComponentProps<typeof Menu.Item>) {
  return (
    <Menu.Item
      className={cn(
        "flex cursor-default select-none items-center gap-2 rounded-md px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-slate-100",
        className,
      )}
      {...props}
    />
  );
}

