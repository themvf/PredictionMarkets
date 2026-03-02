"use client";

import { usePathname, useSearchParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const TIME_RANGES = [
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
  { value: "all", label: "All" },
];

export function TimeRangeSelector() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const current = searchParams.get("range") || "7d";

  function handleClick(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === "7d") {
      params.delete("range");
    } else {
      params.set("range", value);
    }
    router.replace(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex gap-1">
      {TIME_RANGES.map((r) => (
        <Button
          key={r.value}
          variant={current === r.value ? "default" : "outline"}
          size="sm"
          onClick={() => handleClick(r.value)}
          className={cn("text-xs", current === r.value && "pointer-events-none")}
        >
          {r.label}
        </Button>
      ))}
    </div>
  );
}
