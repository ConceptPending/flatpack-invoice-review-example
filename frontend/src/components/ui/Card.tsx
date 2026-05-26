import { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated";
}

export function Card({
  variant = "default",
  className = "",
  ...props
}: CardProps) {
  const base =
    variant === "elevated"
      ? "bg-surface-elevated border border-border rounded-xl shadow-panel"
      : "bg-surface border border-border rounded-xl";

  return <div className={`${base} ${className}`} {...props} />;
}
