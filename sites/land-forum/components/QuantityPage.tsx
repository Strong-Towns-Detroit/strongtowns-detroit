import type { Metadata } from "next";
import Link from "next/link";
import PublicationNav from "./PublicationNav";
import QuantityExplorer from "./QuantityExplorer";
import type {
  QuantityMapConfig,
  QuantitySummary,
} from "../lib/atlas/specs/quantity";

export function quantityMetadata(
  config: QuantityMapConfig,
  summary: QuantitySummary,
): Metadata {
  const share = Math.round(summary.topTenPercentLandValueShare * 100);
  const description =
    `${share}% of Detroit's recorded assessed value sits on 10% of recorded ` +
    `parcel acreage. Explore all ${summary.totalParcels.toLocaleString()} ` +
    `parcels by assessed value per acre.`;
  const url = `/publications/${config.slug}/`;
  return {
    title: config.title,
    description,
    alternates: { canonical: url },
    openGraph: { type: "article", url, title: config.title, description },
    twitter: { card: "summary_large_image", title: config.title, description },
  };
}

export default function QuantityPage({
  config,
  summary,
}: {
  config: QuantityMapConfig;
  summary: QuantitySummary;
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
      <QuantityExplorer config={config} summary={summary} />
    </main>
  );
}
