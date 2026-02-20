"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
export default function CrawlPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/playground?endpoint=crawl"); }, [router]);
  return null;
}
