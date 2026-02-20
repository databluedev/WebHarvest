"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
export default function ScrapePage() {
  const router = useRouter();
  useEffect(() => { router.replace("/playground?endpoint=scrape"); }, [router]);
  return null;
}
