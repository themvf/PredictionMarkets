"use client";

import { usePathname, useSearchParams, useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { useCallback, useState, useTransition } from "react";

interface FilterOption {
  value: string;
  label: string;
}

interface FilterSelectProps {
  paramKey: string;
  label: string;
  options: FilterOption[];
  defaultValue?: string;
}

export function FilterSelect({
  paramKey,
  label,
  options,
  defaultValue = "all",
}: FilterSelectProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const current = searchParams.get(paramKey) || defaultValue;

  function handleChange(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === defaultValue) {
      params.delete(paramKey);
    } else {
      params.set(paramKey, value);
    }
    params.delete("page"); // Reset page on filter change
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      <Select value={current} onValueChange={handleChange}>
        <SelectTrigger className="w-[150px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((opt) => (
            <SelectItem key={opt.value} value={opt.value}>
              {opt.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

interface SearchInputProps {
  paramKey?: string;
  placeholder?: string;
}

export function SearchInput({
  paramKey = "search",
  placeholder = "Search...",
}: SearchInputProps) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [value, setValue] = useState(searchParams.get(paramKey) || "");

  const handleSearch = useCallback(
    (newValue: string) => {
      setValue(newValue);
      startTransition(() => {
        const params = new URLSearchParams(searchParams.toString());
        if (newValue) {
          params.set(paramKey, newValue);
        } else {
          params.delete(paramKey);
        }
        params.delete("page");
        router.push(`${pathname}?${params.toString()}`);
      });
    },
    [pathname, searchParams, router, paramKey]
  );

  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-muted-foreground">
        Search
      </label>
      <Input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => handleSearch(e.target.value)}
        className="w-[200px]"
      />
    </div>
  );
}
