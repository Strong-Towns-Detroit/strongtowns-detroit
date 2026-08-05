import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Page not found",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <main id="main">
      <header className="site-header">
        <Link className="wordmark" href="/" aria-label="Land Forum home">
          LAND FORUM
        </Link>
        <nav aria-label="Primary">
          <Link href="/atlas">BZA Atlas</Link>
          <Link href="/#about">About</Link>
        </nav>
      </header>

      <section className="notfound">
        <p className="kicker">404 · NOT FOUND</p>
        <h1>This page isn&rsquo;t part of the record.</h1>
        <p>
          The address you followed doesn&rsquo;t match anything published here.
          It may have moved, or it may never have existed.
        </p>
        <div className="hero-actions">
          <Link className="button button-primary" href="/">
            Back to Land Forum
          </Link>
          <Link className="button button-quiet" href="/atlas">
            Open the BZA Atlas
          </Link>
        </div>
      </section>

      <footer>
        <div className="footer-top">
          <div className="wordmark footer-mark">LAND FORUM</div>
          <p>Built in Detroit.</p>
        </div>
      </footer>
    </main>
  );
}
