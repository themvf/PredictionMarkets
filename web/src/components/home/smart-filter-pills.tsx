"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  Waves,
  Clock,
  Scale,
  TrendingUp,
  Flame,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { SMART_FILTERS } from "@/lib/constants";

const ICONS: Record<string, React.ElementType> = {
  Waves,
  Clock,
  Scale,
  TrendingUp,
  Flame,
};

export function SmartFilterPills() {
  const searchParams = useSearchParams();
  const activeFilter = searchParams.get("filter");

  return (
    <div className="mx-auto mt-8 flex max-w-3xl flex-wrap justify-center gap-2 px-4">
      {SMART_FILTERS.map((f) => {
        const Icon = ICONS[f.icon];
        const isActive = activeFilter === f.key;
        return (
          <Link
            key={f.key}
            href={isActive ? "/" : `/?filter=${f.key}`}
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-4 py-1.5 text-sm font-medium transition-colors",
              isActive
                ? f.activeClassName
                : "border-border text-muted-foreground hover:border-foreground/30 hover:text-foreground"
            )}
          >
            {Icon && <Icon className="h-3.5 w-3.5" />}
            {f.label}
          </Link>
        );
      })}
    </div>
  );
}
