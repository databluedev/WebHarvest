"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/sidebar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { History } from "lucide-react";
import { api } from "@/lib/api";

export default function JobsPage() {
  const router = useRouter();

  useEffect(() => {
    if (!api.getToken()) router.push("/auth/login");
  }, [router]);

  return (
    <div className="flex h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <div className="mb-6">
            <h1 className="text-3xl font-bold">Job History</h1>
            <p className="text-muted-foreground">View all your past scrape, crawl, and map jobs</p>
          </div>

          <Card>
            <CardContent className="flex flex-col items-center justify-center py-16 text-center">
              <History className="h-12 w-12 text-muted-foreground mb-4" />
              <p className="text-lg font-medium">Job history coming soon</p>
              <p className="text-sm text-muted-foreground mt-1">
                A full history of all your jobs with filtering, search, and export will be available here.
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                For now, track crawl jobs from the Crawl page.
              </p>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
