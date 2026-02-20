"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import {
  Download,
  Loader2,
  ChevronDown,
  FolderArchive,
  FileJson,
  FileSpreadsheet,
} from "lucide-react";

const formatConfig = {
  zip: {
    icon: FolderArchive,
    color: "text-blue-400",
    label: "ZIP Archive",
    description: "Markdown, HTML, screenshots per page",
  },
  json: {
    icon: FileJson,
    color: "text-amber-400",
    label: "JSON",
    description: "Full structured data",
  },
  csv: {
    icon: FileSpreadsheet,
    color: "text-emerald-400",
    label: "CSV Spreadsheet",
    description: "URL, title, word count, metadata",
  },
};

interface ExportDropdownProps {
  onExport: (format: "zip" | "json" | "csv") => Promise<void> | void;
  formats?: ("zip" | "json" | "csv")[];
  disabled?: boolean;
}

export function ExportDropdown({
  onExport,
  formats = ["zip", "json", "csv"],
  disabled,
}: ExportDropdownProps) {
  const [open, setOpen] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const handleExport = async (format: "zip" | "json" | "csv") => {
    setExporting(format);
    setOpen(false);
    try {
      await onExport(format);
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(!open)}
        disabled={disabled || !!exporting}
        className="gap-1.5"
      >
        {exporting ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Download className="h-4 w-4" />
        )}
        {exporting ? `Exporting ${exporting.toUpperCase()}...` : "Download"}
        <ChevronDown className="h-3 w-3 ml-0.5" />
      </Button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-56 rounded-lg border border-border bg-popover shadow-lg z-50 py-1 animate-scale-in">
          {formats.map((fmt) => {
            const config = formatConfig[fmt];
            const Icon = config.icon;
            return (
              <button
                key={fmt}
                onClick={() => handleExport(fmt)}
                className="flex items-center gap-3 w-full px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
              >
                <Icon className={`h-4 w-4 ${config.color}`} />
                <div>
                  <div className="font-medium text-[13px]">{config.label}</div>
                  <div className="text-[11px] text-muted-foreground">
                    {config.description}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
