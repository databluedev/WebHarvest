"use client";

import { useEffect, useState } from "react";
import { Sun, Moon, Monitor } from "lucide-react";

type Theme = "light" | "dark" | "system";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = localStorage.getItem("wh_theme") as Theme | null;
    if (stored) {
      setTheme(stored);
      applyTheme(stored);
    }
  }, []);

  const applyTheme = (t: Theme) => {
    const root = document.documentElement;
    if (t === "system") {
      const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      root.classList.toggle("dark", prefersDark);
      root.classList.toggle("light", !prefersDark);
    } else {
      root.classList.toggle("dark", t === "dark");
      root.classList.toggle("light", t === "light");
    }
  };

  const cycleTheme = () => {
    const order: Theme[] = ["dark", "light", "system"];
    const next = order[(order.indexOf(theme) + 1) % order.length];
    setTheme(next);
    localStorage.setItem("wh_theme", next);
    applyTheme(next);
  };

  const icon =
    theme === "dark" ? <Moon className="h-3.5 w-3.5" /> :
    theme === "light" ? <Sun className="h-3.5 w-3.5" /> :
    <Monitor className="h-3.5 w-3.5" />;

  const label =
    theme === "dark" ? "Dark" :
    theme === "light" ? "Light" :
    "System";

  return (
    <button
      onClick={cycleTheme}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium font-mono text-muted-foreground transition-all duration-200 hover:bg-accent hover:text-foreground border border-transparent"
      title={`Theme: ${label}`}
    >
      {icon}
      {label}
    </button>
  );
}
