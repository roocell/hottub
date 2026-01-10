import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="min-h-screen p-6">
      <div className="mx-auto max-w-xl space-y-4">
        <h1 className="text-3xl font-semibold">LAN Hot Tub Controller</h1>
        <p className="text-sm text-muted-foreground">
          Frontend scaffold is ready. Hook up engine state next.
        </p>
        <Button>Get started</Button>
      </div>
    </main>
  );
}
