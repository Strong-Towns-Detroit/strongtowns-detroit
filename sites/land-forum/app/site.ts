/**
 * Single source of truth for anything that needs to know where the site lives.
 *
 * The public origin is not decided yet. Everything that needs an absolute URL
 * — canonical links, Open Graph tags, the sitemap, robots.txt — reads it from
 * here, so pointing the site at a real domain is one environment variable:
 *
 *   NEXT_PUBLIC_SITE_URL=https://your-domain.org npm run build
 *
 * Until that is set, absolute URLs fall back to localhost. Link previews will
 * not resolve, which is the correct failure: it is visible rather than silently
 * baking a wrong hostname into shipped metadata.
 */

const FALLBACK_ORIGIN = "http://localhost:3000";

function readOrigin(): string {
  const raw = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  if (!raw) return FALLBACK_ORIGIN;
  try {
    // Normalise away a trailing slash and validate early, so a typo surfaces at
    // build time rather than as a malformed <link rel="canonical">.
    return new URL(raw).origin;
  } catch {
    throw new Error(
      `NEXT_PUBLIC_SITE_URL is not a valid absolute URL: ${JSON.stringify(raw)}`,
    );
  }
}

export const siteOrigin = readOrigin();

/** True once a real public domain has been configured. */
export const hasPublicOrigin = siteOrigin !== FALLBACK_ORIGIN;

export const site = {
  name: "Land Forum",
  shortName: "Land Forum",
  title: "Land Forum — Detroit",
  tagline: "Detroit’s zoning appeals, mapped and explained.",
  description:
    "Detroit Board of Zoning Appeals minutes, mapped and explained. Explore cases, read source records, and create graphics with Land Forum.",
  locale: "en_US",
  themeColor: "#0c2340",
  origin: siteOrigin,
  ogImage: "/og-default.png",
  ogImageAlt:
    "Land Forum — public land-use research in Detroit, set in navy on cream.",
} as const;

/**
 * Routes that belong in the sitemap, most important first.
 *
 * Publication render targets (the /poster/ routes) are deliberately absent —
 * they carry `robots: noindex` and exist to be captured, not read.
 */
export const routes = [
  { path: "/", changeFrequency: "monthly" as const, priority: 1 },
  { path: "/atlas/", changeFrequency: "monthly" as const, priority: 0.8 },
  { path: "/methods/", changeFrequency: "monthly" as const, priority: 0.6 },
];

export function absoluteUrl(path: string): string {
  return new URL(path, siteOrigin).toString();
}
