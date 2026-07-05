import { Link } from "wouter";
import { CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertCircle, Home } from "lucide-react";
import { PageShell, SurfaceCard } from "@/components/page-shell";

export default function NotFound() {
  return (
    <PageShell maxWidth="4xl" className="min-h-[70vh] flex items-center justify-center">
      <SurfaceCard className="w-full max-w-md">
        <CardContent className="pt-8 pb-8 text-center space-y-4">
          <div className="mx-auto w-14 h-14 rounded-full bg-rose-500/10 border border-rose-500/20 flex items-center justify-center">
            <AlertCircle className="h-7 w-7 text-rose-400" />
          </div>
          <div className="space-y-2">
            <h1 className="text-2xl font-bold tracking-tight">Page not found</h1>
            <p className="text-sm text-muted-foreground">
              The page you&apos;re looking for doesn&apos;t exist or has been moved.
            </p>
          </div>
          <Link href="/">
            <Button variant="outline" className="gap-2">
              <Home className="w-4 h-4" />
              Back to Dashboard
            </Button>
          </Link>
        </CardContent>
      </SurfaceCard>
    </PageShell>
  );
}
