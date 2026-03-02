"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Search } from "lucide-react";

export function TraderSearchForm() {
  const [value, setValue] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;

    // If it looks like a wallet address, go directly to the profile
    if (trimmed.startsWith("0x") && trimmed.length > 10) {
      router.push(`/traders/${trimmed}`);
    } else {
      // Otherwise search by username
      router.push(`/traders?q=${encodeURIComponent(trimmed)}`);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 max-w-lg">
      <Input
        type="text"
        placeholder="Username or wallet address (0x...)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="flex-1"
      />
      <Button type="submit">
        <Search className="mr-2 h-4 w-4" />
        Search
      </Button>
    </form>
  );
}
