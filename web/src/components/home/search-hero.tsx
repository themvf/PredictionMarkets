"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";

export function SearchHero() {
  const [value, setValue] = useState("");
  const router = useRouter();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;

    if (/^0x[0-9a-fA-F]{40,}$/.test(trimmed)) {
      router.push(`/traders/${trimmed}`);
    } else {
      router.push(`/?search=${encodeURIComponent(trimmed)}`);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="mx-auto mt-6 max-w-2xl px-4"
    >
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="text"
          placeholder="Search markets by title, category, or keyword..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="h-12 pl-10 text-base"
        />
      </div>
    </form>
  );
}
