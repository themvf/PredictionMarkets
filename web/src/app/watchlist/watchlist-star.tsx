"use client";

import { useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Star } from "lucide-react";
import { toggleWatchlistAction } from "./actions";

export function WatchlistStar({
  traderId,
  watched,
}: {
  traderId: number;
  watched: boolean;
}) {
  const [isPending, startTransition] = useTransition();

  return (
    <Button
      variant="ghost"
      size="icon"
      disabled={isPending}
      onClick={() => {
        startTransition(() => toggleWatchlistAction(traderId, watched));
      }}
      title={watched ? "Remove from watchlist" : "Add to watchlist"}
    >
      <Star
        className={`h-4 w-4 ${watched ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground"}`}
      />
    </Button>
  );
}
