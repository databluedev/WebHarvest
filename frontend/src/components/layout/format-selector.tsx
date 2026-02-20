"use client";

import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import {
  FileText,
  AlignLeft,
  Link2,
  Code,
  Camera,
  Braces,
  Fingerprint,
  Image as ImageIcon,
  X,
  Pencil,
} from "lucide-react";

export type FormatOption = {
  id: string;
  label: string;
  icon: any;
  subOptions?: { id: string; label: string }[];
};

const FORMAT_OPTIONS: FormatOption[] = [
  { id: "markdown", label: "Markdown", icon: FileText },
  { id: "headings", label: "Summary", icon: AlignLeft },
  { id: "links", label: "Links", icon: Link2 },
  {
    id: "html",
    label: "HTML",
    icon: Code,
    subOptions: [
      { id: "cleaned", label: "Cleaned" },
      { id: "raw", label: "Raw" },
    ],
  },
  {
    id: "screenshot",
    label: "Screenshot",
    icon: Camera,
    subOptions: [
      { id: "viewport", label: "Viewport" },
      { id: "fullpage", label: "Full Page" },
    ],
  },
  {
    id: "structured_data",
    label: "JSON",
    icon: Braces,
  },
  { id: "branding", label: "Branding", icon: Fingerprint },
  { id: "images", label: "Images", icon: ImageIcon },
];

interface FormatSelectorProps {
  open: boolean;
  onClose: () => void;
  selectedFormats: string[];
  onToggleFormat: (format: string) => void;
  htmlMode?: "cleaned" | "raw";
  onHtmlModeChange?: (mode: "cleaned" | "raw") => void;
  screenshotMode?: "viewport" | "fullpage";
  onScreenshotModeChange?: (mode: "viewport" | "fullpage") => void;
}

export function FormatSelector({
  open,
  onClose,
  selectedFormats,
  onToggleFormat,
  htmlMode = "cleaned",
  onHtmlModeChange,
  screenshotMode = "fullpage",
  onScreenshotModeChange,
}: FormatSelectorProps) {
  const panelRef = useRef<HTMLDivElement>(null!);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      className="absolute top-10 left-0 z-50 w-72 rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/30 animate-scale-in overflow-hidden"
      style={{ transformOrigin: "top left" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border/40">
        <span className="text-sm font-semibold">Format</span>
        <button
          onClick={onClose}
          className="h-6 w-6 rounded-md grid place-items-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Options */}
      <div className="py-1">
        {FORMAT_OPTIONS.map((fmt) => {
          const isSelected = selectedFormats.includes(fmt.id);
          const Icon = fmt.icon;

          return (
            <div key={fmt.id}>
              <button
                onClick={() => onToggleFormat(fmt.id)}
                className={cn(
                  "flex items-center gap-3 w-full px-4 py-2.5 text-left transition-colors",
                  isSelected
                    ? "bg-muted/50"
                    : "hover:bg-muted/30"
                )}
              >
                {/* Checkbox */}
                <div
                  className={cn(
                    "h-4 w-4 rounded border-[1.5px] grid place-items-center transition-colors shrink-0",
                    isSelected
                      ? "bg-primary border-primary"
                      : "border-muted-foreground/30"
                  )}
                >
                  {isSelected && (
                    <svg className="h-2.5 w-2.5 text-primary-foreground" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </div>

                <Icon className="h-4 w-4 text-muted-foreground shrink-0" />
                <span className="text-[13px] font-medium flex-1">{fmt.label}</span>

                {/* Sub-options for HTML */}
                {fmt.id === "html" && isSelected && fmt.subOptions && (
                  <div className="flex rounded-md overflow-hidden border border-border/40">
                    {fmt.subOptions.map((sub) => (
                      <button
                        key={sub.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          onHtmlModeChange?.(sub.id as "cleaned" | "raw");
                        }}
                        className={cn(
                          "px-2.5 py-0.5 text-[10px] font-medium transition-colors",
                          htmlMode === sub.id
                            ? "bg-muted text-foreground"
                            : "text-muted-foreground/50 hover:text-muted-foreground"
                        )}
                      >
                        {sub.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Sub-options for Screenshot */}
                {fmt.id === "screenshot" && isSelected && fmt.subOptions && (
                  <div className="flex rounded-md overflow-hidden border border-border/40">
                    {fmt.subOptions.map((sub) => (
                      <button
                        key={sub.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          onScreenshotModeChange?.(sub.id as "viewport" | "fullpage");
                        }}
                        className={cn(
                          "px-2.5 py-0.5 text-[10px] font-medium transition-colors",
                          screenshotMode === sub.id
                            ? "bg-muted text-foreground"
                            : "text-muted-foreground/50 hover:text-muted-foreground"
                        )}
                      >
                        {sub.label}
                      </button>
                    ))}
                  </div>
                )}

                {/* Edit options for JSON */}
                {fmt.id === "structured_data" && isSelected && (
                  <button
                    onClick={(e) => e.stopPropagation()}
                    className="flex items-center gap-1 px-2 py-0.5 rounded-md border border-border/40 text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Pencil className="h-2.5 w-2.5" />
                    Edit options
                  </button>
                )}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
