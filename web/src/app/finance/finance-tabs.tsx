"use client";

import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";

const TABS = [
  { value: "markets", label: "Markets" },
  { value: "whales", label: "Whale Activity" },
  { value: "sharp", label: "Sharp Money" },
] as const;

export function FinanceTabs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const current = searchParams.get("tab") || "markets";

  function handleClick(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "markets") {
      params.delete("tab");
    } else {
      params.set("tab", value);
    }
    // Reset page when switching tabs
    params.delete("page");
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex border-b">
      {TABS.map((tab) => (
        <button
          key={tab.value}
          onClick={() => handleClick(tab.value)}
          className={cn(
            "px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors",
            current === tab.value
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
