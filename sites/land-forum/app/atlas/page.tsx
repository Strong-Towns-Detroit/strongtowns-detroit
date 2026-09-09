import type { Metadata } from "next";
import Link from "next/link";
import AtlasExplorer from "../../components/AtlasExplorer";

const title = "Detroit BZA Atlas";
const description =
  "Search and filter Detroit Board of Zoning Appeals cases from 2019 to 2026 " +
  "by address, petitioner, case number, request type, outcome, and year — " +
  "mapped from the published meeting minutes.";

export const metadata: Metadata = {
  title,
  description,
  alternates: { canonical: "/atlas/" },
  openGraph: {
    type: "article",
    url: "/atlas/",
    title,
    description,
  },
  twitter: { card: "summary_large_image", title, description },
};

export default function AtlasPage() {
  return (
    <main className="atlas-page" id="main">
      <header className="site-header atlas-header">
        <Link className="wordmark" href="/" aria-label="Land Forum home">
          LAND FORUM
        </Link>
        <nav aria-label="Primary">
          <Link className="active" aria-current="page" href="/atlas">
            BZA Atlas
          </Link>
          <Link href="/#about">About</Link>
          <Link href="/graphics/bza/">Create a graphic</Link>
        </nav>
      </header>
      <section className="atlas-intro">
        <p className="kicker">DETROIT BOARD OF ZONING APPEALS · 2019–2026</p>
        <h1>Find the cases behind the map.</h1>
        <p>
          Search by address, petitioner, or case number. Filter the public
          record by request, outcome, and year.
        </p>
      </section>
      <AtlasExplorer />
    </main>
  );
}
