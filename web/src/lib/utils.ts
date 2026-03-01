import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { formatDistanceToNow, format } from "date-fns"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a number as USD currency: $1,234.56 */
export function formatCurrency(
  value: number | null | undefined,
  decimals = 2
): string {
  if (value == null || isNaN(value)) return "—"
  return `$${value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`
}

/** Format a number as compact currency: $1.2M, $500K */
export function formatCompactCurrency(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "—"
  return `$${Intl.NumberFormat("en-US", { notation: "compact" }).format(value)}`
}

/** Format a price as $0.650 (3 decimals for prediction market prices) */
export function formatPrice(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "—"
  return `$${value.toFixed(3)}`
}

/** Format a percentage: 12.3% */
export function formatPercent(value: number | null | undefined): string {
  if (value == null || isNaN(value)) return "—"
  return `${(value * 100).toFixed(1)}%`
}

/**
 * Parse an ISO/timestamp string and return "3 hours ago" style text.
 * Falls back to the raw string if unparseable.
 */
export function formatRelativeTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—"
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return formatDistanceToNow(date, { addSuffix: true })
  } catch {
    return dateStr
  }
}

/** Parse an ISO string and return "Jan 15, 2025 3:42 PM" */
export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return "—"
  try {
    const date = new Date(dateStr)
    if (isNaN(date.getTime())) return dateStr
    return format(date, "MMM d, yyyy h:mm a")
  } catch {
    return dateStr
  }
}
