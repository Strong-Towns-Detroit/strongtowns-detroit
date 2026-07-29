import Link from "next/link";

export default function Home() {
  return (
    <main>
      <header className="site-header">
        <Link className="wordmark" href="/" aria-label="Land Forum home">
          LAND FORUM
        </Link>
        <nav aria-label="Primary navigation">
          <Link href="/atlas">BZA Atlas</Link>
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

      <section className="project-band">
        <p className="kicker">FIRST PUBLICATION</p>
        <div className="project-grid">
          <div>
            <h2>Detroit BZA Atlas</h2>
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

      <section className="about" id="about">
        <p className="kicker">THE PROPOSITION</p>
        <div>
          <h2>A genuine forum begins with evidence—and remains open to argument.</h2>
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
        <div className="wordmark footer-mark">LAND FORUM</div>
        <p>Built in Detroit. Institutional partnerships are still being formed.</p>
      </footer>
    </main>
  );
}
