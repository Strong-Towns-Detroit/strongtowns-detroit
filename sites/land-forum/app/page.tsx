import Link from "next/link";
import { absoluteUrl, site } from "./site";

const structuredData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": absoluteUrl("/#website"),
      url: absoluteUrl("/"),
      name: site.name,
      description: site.description,
      inLanguage: "en-US",
    },
    {
      "@type": "Dataset",
      "@id": absoluteUrl("/atlas/#dataset"),
      name: "Detroit Board of Zoning Appeals case records, 2019–2026",
      description:
        "Case-level records extracted from published Detroit Board of Zoning " +
        "Appeals meeting minutes, including petitioner, location, request " +
        "type, and decision.",
      url: absoluteUrl("/atlas/"),
      isAccessibleForFree: true,
      creator: { "@type": "Organization", name: site.name },
      spatialCoverage: "Detroit, Michigan",
      temporalCoverage: "2019/2026",
    },
  ],
};

export default function Home() {
  return (
    <main id="main">
      <script
        type="application/ld+json"
        // Static, author-controlled object — not user input.
        dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
      />

      <header className="site-header">
        <Link className="wordmark" href="/" aria-label="Land Forum home">
          LAND FORUM
        </Link>
        <nav aria-label="Primary">
          <Link href="/atlas">BZA Atlas</Link>
          <Link href="/graphics/bza/">Create a graphic</Link>
          <a href="#about">About</a>
        </nav>
      </header>

      <section className="hero">
        <div className="hero-copy">
          <p className="kicker">DETROIT · PUBLIC LAND-USE RESEARCH</p>
          <h1>
            A forum for
            <br />
            <em>building Detroit.</em>
          </h1>
          <p className="hero-dek">
            A forum for examining the rules, decisions, histories, and
            possibilities that shape Detroit—together.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" href="/atlas">
              Explore BZA cases
            </Link>
            <a className="button button-quiet" href="#about">
              Why Land Forum?
            </a>
          </div>
        </div>
        <div className="hero-field" aria-hidden="true">
          <div className="field-line field-line-one" />
          <div className="field-line field-line-two" />
          <div className="field-dot dot-one" />
          <div className="field-dot dot-two" />
          <div className="field-dot dot-three" />
          <p>LAND IS NEVER<br />JUST A SURFACE.</p>
        </div>
      </section>

      <section className="project-band" aria-labelledby="first-publication">
        <p className="kicker">FIRST PUBLICATION</p>
        <div className="project-grid">
          <div>
            <h2 id="first-publication">Detroit BZA Atlas</h2>
            <p>
              Search and examine Board of Zoning Appeals cases recorded in
              public meeting minutes from 2019 through 2026.
            </p>
          </div>
          <dl>
            <div><dt>405</dt><dd>case histories</dd></div>
            <div><dt>496</dt><dd>hearing appearances</dd></div>
            <div><dt>2019–26</dt><dd>minutes reviewed</dd></div>
          </dl>
          <Link className="project-link" href="/atlas">
            Open the atlas <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </section>

      <section className="project-band" aria-labelledby="lot-area">
        <p className="kicker">PARCEL GEOMETRY</p>
        <div className="project-grid">
          <div>
            <h2 id="lot-area">Detroit’s residential lot minimums</h2>
            <p>
              Every recorded residential parcel in Detroit, measured against
              the minimum lot area and the minimum lot width in force today.
              Select any parcel to see its own numbers.
            </p>
          </div>
          <dl>
            <div><dt>69%</dt><dd>below the 5,000-sq.-ft. area</dd></div>
            <div><dt>378,366</dt><dd>parcels mapped</dd></div>
            <div><dt>88%</dt><dd>below the 50-ft. width</dd></div>
          </dl>
          <Link className="project-link" href="/publications/minimum-lot-area">
            Open the map <span aria-hidden="true">↗</span>
          </Link>
        </div>
      </section>

      <section className="about" id="about" aria-labelledby="proposition">
        <p className="kicker">THE PROPOSITION</p>
        <div>
          <h2 id="proposition">
            A genuine forum begins with evidence—and remains open to argument.
          </h2>
          <div className="about-columns">
            <p>
              Land Forum is being built as civic infrastructure: a place where
              residents, practitioners, students, institutions, and public
              officials can encounter the same facts and ask better questions.
            </p>
            <p>
              This early site begins with zoning appeals. Future work may
              include access, parcel rules, historical plans, taxation, and
              projects contributed by Detroit communities.
            </p>
          </div>
        </div>
      </section>

      <footer>
        <div className="footer-top">
          <div className="wordmark footer-mark">LAND FORUM</div>
          <p>
            Built in Detroit. Institutional partnerships are still being
            formed.
          </p>
        </div>
        <div className="footer-meta">
          <p>
            © {new Date().getFullYear()} Land Forum. Case records are derived
            from published City of Detroit Board of Zoning Appeals meeting
            minutes and are provided without warranty as to accuracy or
            completeness.
          </p>
          <nav aria-label="Footer">
            <Link href="/atlas">BZA Atlas</Link>
            <a href="#about">About</a>
            <a href="https://detroitmi.gov/government/boards/board-zoning-appeals">
              Source: City of Detroit BZA
            </a>
          </nav>
        </div>
      </footer>
    </main>
  );
}
