"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Store,
  GitCompare,
  LineChart,
  Bell,
  Brain,
  Bot,
  Trophy,
  Waves,
  User,
  Sparkles,
  Star,
  Menu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger, SheetTitle } from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "./theme-toggle";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/markets", label: "Markets", icon: Store },
  { href: "/cross-platform", label: "Cross-Platform", icon: GitCompare },
  { href: "/charts", label: "Price Charts", icon: LineChart },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/insights", label: "AI Insights", icon: Brain },
  { href: "/agents", label: "Agent Status", icon: Bot },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { href: "/whales", label: "Whale Tracker", icon: Waves },
  { href: "/first-time", label: "First-Time Trades", icon: Sparkles },
  { href: "/watchlist", label: "Watchlist", icon: Star },
] as const;

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="flex flex-col gap-1 px-2">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const isActive =
          href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4 shrink-0" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

/** Desktop sidebar — hidden on mobile */
export function Sidebar() {
  return (
    <aside className="hidden md:flex md:w-56 md:flex-col md:border-r md:bg-card">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <LineChart className="h-5 w-5 text-primary" />
        <span className="font-semibold tracking-tight">PredictBoard</span>
      </div>
      <ScrollArea className="flex-1 py-3">
        <NavLinks />
      </ScrollArea>
      <div className="border-t p-2">
        <ThemeToggle />
      </div>
    </aside>
  );
}

/** Mobile top bar with sheet-based nav */
export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <header className="flex h-14 items-center gap-3 border-b bg-card px-4 md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon">
            <Menu className="h-5 w-5" />
            <span className="sr-only">Toggle navigation</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="w-56 p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <div className="flex h-14 items-center gap-2 border-b px-4">
            <LineChart className="h-5 w-5 text-primary" />
            <span className="font-semibold tracking-tight">PredictBoard</span>
          </div>
          <ScrollArea className="h-[calc(100vh-3.5rem)] py-3">
            <NavLinks onNavigate={() => setOpen(false)} />
          </ScrollArea>
        </SheetContent>
      </Sheet>
      <span className="font-semibold tracking-tight">PredictBoard</span>
      <div className="ml-auto">
        <ThemeToggle />
      </div>
    </header>
  );
}
