"use client";

import { useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Check } from "lucide-react";
import { acknowledgeAlertAction } from "./actions";

export function AcknowledgeButton({ alertId }: { alertId: number }) {
  const [isPending, startTransition] = useTransition();

  return (
    <Button
      variant="outline"
      size="sm"
      disabled={isPending}
      onClick={() => {
        startTransition(() => acknowledgeAlertAction(alertId));
      }}
    >
      <Check className="mr-1 h-3 w-3" />
      {isPending ? "Acknowledging..." : "Acknowledge"}
    </Button>
  );
}
