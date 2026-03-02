"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
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
  MoreHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTrigger,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "./theme-toggle";

const PRIMARY_NAV = [
  { href: "/markets", label: "Markets", icon: Store },
  { href: "/cross-platform", label: "Cross-Platform", icon: GitCompare },
  { href: "/charts", label: "Charts", icon: LineChart },
  { href: "/alerts", label: "Alerts", icon: Bell },
  { href: "/whales", label: "Whales", icon: Waves },
  { href: "/traders", label: "Traders", icon: User },
] as const;

const MORE_NAV = [
  { href: "/insights", label: "AI Insights", icon: Brain },
  { href: "/agents", label: "Agents", icon: Bot },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { href: "/first-time", label: "First-Time", icon: Sparkles },
  { href: "/watchlist", label: "Watchlist", icon: Star },
] as const;

const ALL_NAV = [...PRIMARY_NAV, ...MORE_NAV];

function isActive(href: string, pathname: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function TopNav() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        {/* Brand */}
        <Link href="/" className="flex items-center gap-2 shrink-0">
          <LineChart className="h-5 w-5 text-primary" />
          <span className="font-semibold tracking-tight">PredictBoard</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1 ml-6">
          {PRIMARY_NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors rounded-md",
                isActive(href, pathname)
                  ? "text-primary"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
            </Link>
          ))}

          {/* More dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium transition-colors rounded-md",
                  MORE_NAV.some((item) => isActive(item.href, pathname))
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <MoreHorizontal className="h-4 w-4" />
                More
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {MORE_NAV.map(({ href, label, icon: Icon }) => (
                <DropdownMenuItem key={href} asChild>
                  <Link
                    href={href}
                    className={cn(
                      "flex items-center gap-2",
                      isActive(href, pathname) && "text-primary"
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </nav>

        {/* Right side */}
        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />

          {/* Mobile hamburger */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle navigation</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="w-64 p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <div className="flex h-14 items-center gap-2 border-b px-4">
                <LineChart className="h-5 w-5 text-primary" />
                <span className="font-semibold tracking-tight">
                  PredictBoard
                </span>
              </div>
              <ScrollArea className="h-[calc(100vh-3.5rem)] py-3">
                <nav className="flex flex-col gap-1 px-2">
                  {ALL_NAV.map(({ href, label, icon: Icon }) => (
                    <Link
                      key={href}
                      href={href}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive(href, pathname)
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4 shrink-0" />
                      {label}
                    </Link>
                  ))}
                </nav>
              </ScrollArea>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
