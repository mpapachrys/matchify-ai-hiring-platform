"use client";

import * as LabelPrimitive from "@radix-ui/react-label";
import { ChevronDown, Eye, EyeOff } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const controlBase =
  "w-full rounded-lg border border-border bg-surface-2/60 px-3 text-sm text-foreground placeholder:text-subtle transition-colors hover:border-border-strong focus:border-primary disabled:opacity-60";

export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> & { required?: boolean }
>(({ className, children, required, ...props }, ref) => (
  <LabelPrimitive.Root
    ref={ref}
    className={cn("mb-1.5 block text-xs font-medium text-muted", className)}
    {...props}
  >
    {required ? <span className="mr-1 text-danger">*</span> : null}
    {children}
  </LabelPrimitive.Root>
));
Label.displayName = "Label";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input ref={ref} className={cn(controlBase, "h-10", className)} {...props} />
  ),
);
Input.displayName = "Input";

/**
 * A password field that can be revealed.
 *
 * Masking protects against someone reading the screen, which is rarely the
 * actual threat while signing in alone on a laptop. What it reliably causes is
 * mistyped passwords the user cannot see to correct. Revealing is the user's
 * call, so this is a real focusable button with its state announced, not a
 * hover-only affordance — and it never touches what gets submitted.
 */
export const PasswordInput = React.forwardRef<
  HTMLInputElement,
  Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">
>(({ className, disabled, id, ...props }, ref) => {
  const [visible, setVisible] = React.useState(false);

  return (
    <div className="relative">
      <Input
        ref={ref}
        id={id}
        type={visible ? "text" : "password"}
        disabled={disabled}
        // Room for the button, so a long password never runs under the icon.
        className={cn("pr-10", className)}
        {...props}
      />
      <button
        // Without an explicit type, a <button> inside a <form> submits it —
        // here that would sign you in on the way to peeking at your password.
        type="button"
        onClick={() => setVisible((value) => !value)}
        disabled={disabled}
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        aria-controls={id}
        // Inset by 1: globals.css draws focus rings with a 2px offset, and at
        // right-0 that ring would sit outside the field's own border.
        className="absolute right-1 top-1 flex size-8 items-center justify-center rounded-md text-subtle transition-colors hover:text-foreground focus-visible:text-foreground disabled:pointer-events-none disabled:opacity-60"
      >
        {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
      </button>
    </div>
  );
});
PasswordInput.displayName = "PasswordInput";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(controlBase, "min-h-24 py-2.5", className)} {...props} />
));
Textarea.displayName = "Textarea";

/**
 * A styled native <select>.
 *
 * Deliberately not a Radix listbox: native gives us keyboard behaviour, mobile
 * pickers, and form integration for free, and nothing in this product needs
 * multi-line options or async loading inside a dropdown.
 */
export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <div className="relative">
    <select
      ref={ref}
      className={cn(controlBase, "h-10 appearance-none pr-9", className)}
      {...props}
    >
      {children}
    </select>
    <ChevronDown className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-subtle" />
  </div>
));
Select.displayName = "Select";

export function FieldError({ children }: { children?: React.ReactNode }) {
  if (!children) return null;
  return <p className="mt-1 text-xs text-danger">{children}</p>;
}

export function Field({
  label,
  htmlFor,
  required,
  error,
  hint,
  children,
  className,
}: {
  label: string;
  htmlFor?: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <Label htmlFor={htmlFor} required={required}>
        {label}
      </Label>
      {children}
      {hint && !error ? <p className="mt-1 text-xs text-subtle">{hint}</p> : null}
      <FieldError>{error}</FieldError>
    </div>
  );
}
