import Link from "next/link";
import { FileQuestion } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Card className="max-w-md text-center">
        <CardHeader className="flex flex-col items-center gap-2">
          <FileQuestion className="h-10 w-10 text-muted-foreground" />
          <CardTitle>Page not found</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            The page you&apos;re looking for doesn&apos;t exist or has been
            moved.
          </p>
          <Button asChild>
            <Link href="/">Back to Dashboard</Link>
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
