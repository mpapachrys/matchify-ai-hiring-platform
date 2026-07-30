"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
  /** Hide the close affordance and ignore outside clicks / Escape. Use while
   *  work is in flight, so a stray click can't abandon a running job. */
  locked = false,
}: {
  className?: string;
  children: React.ReactNode;
  title: string;
  description?: string;
  locked?: boolean;
}) {
  const block = (event: Event) => {
    if (locked) event.preventDefault();
  };

  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm data-[state=open]:animate-in data-[state=open]:fade-in" />
      <DialogPrimitive.Content
        onInteractOutside={block}
        onEscapeKeyDown={block}
        className={cn(
          "panel-solid fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 p-6 shadow-2xl",
          "max-h-[85vh] overflow-y-auto",
          className,
        )}
      >
        <div className="mb-4 pr-8">
          <DialogPrimitive.Title className="text-lg font-bold text-foreground">
            {title}
          </DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-1 text-sm text-muted">
              {description}
            </DialogPrimitive.Description>
          ) : (
            // Radix warns without a description; keep it for screen readers.
            <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
          )}
        </div>
        {children}
        {locked ? null : (
          <DialogPrimitive.Close className="absolute right-4 top-4 rounded-lg p-1.5 text-subtle transition-colors hover:bg-surface-2 hover:text-foreground">
            <X className="size-4" />
            <span className="sr-only">Close</span>
          </DialogPrimitive.Close>
        )}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
