import Link from "next/link";
import AtlasExplorer from "../../components/AtlasExplorer";

export default function AtlasPage() {
  return (
    <main className="atlas-page">
      <header className="site-header atlas-header">
        <Link className="wordmark" href="/">
          LAND FORUM
        </Link>
        <nav aria-label="Primary navigation">
          <Link className="active" href="/atlas">BZA Atlas</Link>
          <Link href="/">About</Link>
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
