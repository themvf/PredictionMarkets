import Link from "next/link";
import { getCategoriesWithCounts } from "@/db/queries/markets";
import { cn } from "@/lib/utils";

export async function CategorySidebar({
  activeCategory,
}: {
  activeCategory?: string;
}) {
  const categories = await getCategoriesWithCounts();
  const total = categories.reduce((sum, c) => sum + Number(c.count), 0);

  return (
    <aside className="hidden lg:block w-56 shrink-0">
      <div className="sticky top-20 space-y-1">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-3 mb-3">
          Category
        </h3>
        <CategoryLink
          label="All Categories"
          count={total}
          href="/"
          active={!activeCategory}
        />
        {categories.map(({ category, count }) =>
          category ? (
            <CategoryLink
              key={category}
              label={category}
              count={Number(count)}
              href={`/?category=${encodeURIComponent(category)}`}
              active={activeCategory === category}
            />
          ) : null
        )}
      </div>
    </aside>
  );
}

function CategoryLink({
  label,
  count,
  href,
  active,
}: {
  label: string;
  count: number;
  href: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
        active
          ? "bg-primary/10 text-primary border-l-2 border-primary"
          : "text-muted-foreground hover:text-foreground hover:bg-accent"
      )}
    >
      <span>{label}</span>
      <span className="font-mono text-xs">{count}</span>
    </Link>
  );
}
