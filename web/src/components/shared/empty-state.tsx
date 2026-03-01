import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: React.ElementType;
  title: string;
  description?: string;
  children?: React.ReactNode;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  children,
}: EmptyStateProps) {
  return (
    <div className="flex min-h-[30vh] flex-col items-center justify-center gap-3 text-center">
      <Icon className="h-10 w-10 text-muted-foreground" />
      <h3 className="text-lg font-medium">{title}</h3>
      {description && (
        <p className="max-w-sm text-sm text-muted-foreground">{description}</p>
      )}
      {children}
    </div>
  );
}
