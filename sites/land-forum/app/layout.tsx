import type { Metadata, Viewport } from "next";
import ReactDOM from "react-dom";
import "./tokens.css";
import "./fonts.css";
import "./styles.css";
import "./globals.css";
import { site, siteOrigin } from "./site";

export const metadata: Metadata = {
  metadataBase: new URL(siteOrigin),
  title: {
    default: site.title,
    // Page titles become "Detroit BZA Atlas — Land Forum" rather than every
    // page sharing the root title, which is what happened before.
    template: `%s — ${site.name}`,
  },
  description: site.description,
  applicationName: site.name,
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: site.name,
    locale: site.locale,
    url: "/",
    title: site.title,
    description: site.description,
    images: [
      {
        url: site.ogImage,
        width: 1200,
        height: 630,
        alt: site.ogImageAlt,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: site.title,
    description: site.description,
    images: [site.ogImage],
  },
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/favicon.ico", sizes: "48x48" },
    ],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  manifest: "/site.webmanifest",
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  themeColor: site.themeColor,
  colorScheme: "light",
};

/**
 * The three faces used above the fold. A self-hosted font is only discovered
 * once the CSS that references it has parsed, which is late enough to show a
 * visible swap on the hero, so these start alongside the stylesheet.
 *
 * The latin-ext subsets are deliberately absent — they are fetched only if a
 * glyph outside Latin-1 actually appears on the page.
 *
 * ReactDOM.preload rather than literal <link> elements: React dedupes these by
 * href, whereas authoring them inside <head> emitted each one twice.
 */
const PRELOADED_FONTS = [
  "/fonts/source-serif-4-latin.woff2",
  "/fonts/source-serif-4-latin-italic.woff2",
  "/fonts/inter-latin.woff2",
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  for (const href of PRELOADED_FONTS) {
    ReactDOM.preload(href, {
      as: "font",
      type: "font/woff2",
      crossOrigin: "anonymous",
    });
  }

  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        {children}
      </body>
    </html>
  );
}
