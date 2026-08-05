import type { Metadata } from "next";
import Link from "next/link";
import ParcelRuleExplorer from "./ParcelRuleExplorer";
import PublicationNav from "./PublicationNav";
import type {
  ParcelRuleConfig,
  ParcelRuleSummary,
} from "../lib/atlas/specs/parcel-rule";

/**
 * The whole interactive publication, shared by every parcel rule.
 *
 * Routes are static directories rather than one `[rule]` segment: vinext's
 * prerenderer probes dynamic routes without a trailing slash, and
 * `trailingSlash: true` answers with a 308, which it reports as
 * "RSC handler returned 308" and refuses to export. `next build` handles it
 * fine, but `npm run build` is the production command, so the routes stay
 * static and each one is five lines over this component.
 */
export function parcelRuleMetadata(
  config: ParcelRuleConfig,
  summary: ParcelRuleSummary,
): Metadata {
  const share = Math.round(summary.belowMinimumShare * 100);
  const description =
    `${share}% of evaluated R1–R6 parcels in Detroit fall below ` +
    `${config.title.replace("Detroit's ", "")}. Explore all ` +
    `${summary.totalParcels.toLocaleString()} parcels and inspect any one of ` +
    `them against the standard.`;
  const url = `/publications/${config.slug}/`;
  return {
    title: config.title,
    description,
    alternates: { canonical: url },
    openGraph: { type: "article", url, title: config.title, description },
    twitter: {
      card: "summary_large_image",
      title: config.title,
      description,
    },
  };
}

export function posterMetadata(config: ParcelRuleConfig): Metadata {
  return {
    title: `${config.title} — board`,
    // A render target, not a page for readers to find.
    robots: { index: false, follow: false },
  };
}

export default function ParcelRulePage({
  config,
  summary,
}: {
  config: ParcelRuleConfig;
  summary: ParcelRuleSummary;
}) {
  return (
    <main className="pub-page" id="main">
      <header className="site-header">
        <Link className="wordmark" href="/" aria-label="Land Forum home">
          LAND FORUM
        </Link>
        <PublicationNav current={config.slug} />
      </header>

      <section className="pub-intro">
        <p className="kicker">{config.kicker}</p>
        <h1>{config.title}</h1>
        <p>{config.standfirst}</p>
      </section>

      <ParcelRuleExplorer config={config} summary={summary} />
    </main>
  );
}
