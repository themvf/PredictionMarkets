"use client";

import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { cn } from "@/lib/utils";
import type { SubcategoryCount } from "@/db/queries/category-hub";

interface EconomySidebarProps {
  counts: SubcategoryCount[];
  totalMarkets: number;
}

export function EconomySidebar({ counts, totalMarkets }: EconomySidebarProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const activeSub = searchParams.get("sub") || "";

  function handleClick(sub: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (sub === "") {
      params.delete("sub");
    } else {
      params.set("sub", sub);
    }
    params.delete("page");
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <nav className="space-y-1">
      <button
        onClick={() => handleClick("")}
        className={cn(
          "w-full flex items-center justify-between px-3 py-2 text-sm rounded-md transition-colors",
          activeSub === ""
            ? "bg-primary/10 text-primary font-medium"
            : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        )}
      >
        <span>All</span>
        <span className="text-xs tabular-nums">{totalMarkets}</span>
      </button>
      {counts.map((item) => (
        <button
          key={item.subcategory}
          onClick={() => handleClick(item.subcategory)}
          className={cn(
            "w-full flex items-center justify-between px-3 py-2 text-sm rounded-md transition-colors",
            activeSub === item.subcategory
              ? "bg-primary/10 text-primary font-medium"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          )}
        >
          <span>{item.subcategory}</span>
          <span className="text-xs tabular-nums">{item.count}</span>
        </button>
      ))}
    </nav>
  );
}
