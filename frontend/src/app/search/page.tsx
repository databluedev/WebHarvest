"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
export default function SearchPage() {
  const router = useRouter();
  useEffect(() => { router.replace("/playground?endpoint=search"); }, [router]);
  return null;
}
