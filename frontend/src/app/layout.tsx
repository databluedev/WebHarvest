import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";

const font = Outfit({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "WebHarvest - Web Crawling Platform",
  description: "Open source web crawling platform with AI-powered extraction. Scrape, crawl, and map websites.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="dns-prefetch" href={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} />
        <link rel="preconnect" href={process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"} crossOrigin="anonymous" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('wh_theme');
                  if (theme === 'light') {
                    document.documentElement.classList.remove('dark');
                    document.documentElement.classList.add('light');
                  } else if (theme === 'system') {
                    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    document.documentElement.classList.toggle('dark', prefersDark);
                    document.documentElement.classList.toggle('light', !prefersDark);
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body className={font.className}>{children}</body>
    </html>
  );
}
