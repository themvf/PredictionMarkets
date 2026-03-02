"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { cn } from "@/lib/utils";
import { CATEGORIES } from "@/lib/constants";

export function CategoryPills() {
  const searchParams = useSearchParams();
  const activeCategory = searchParams.get("category") || "All";

  return (
    <div className="flex flex-wrap justify-center gap-2 px-4">
      {CATEGORIES.map((cat) => {
        const isActive = cat === activeCategory;
        const href =
          cat === "All" ? "/" : `/?category=${encodeURIComponent(cat)}`;
        return (
          <Link
            key={cat}
            href={href}
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-medium transition-colors border",
              isActive
                ? "bg-primary text-primary-foreground border-primary"
                : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/30"
            )}
          >
            {cat === "All" ? "Search All" : cat}
          </Link>
        );
      })}
    </div>
  );
}
