import Link from "next/link";
import { PARCEL_RULES } from "../lib/atlas/specs/rules";
import { QUANTITY_MAPS } from "../lib/atlas/specs/quantities";

/**
 * One nav for every publication, so adding a map cannot leave it reachable
 * from some pages and not others.
 */
export default function PublicationNav({ current }: { current?: string }) {
  const entries = [
    ...Object.values(PARCEL_RULES),
    ...Object.values(QUANTITY_MAPS),
  ];
  return (
    <nav aria-label="Primary">
      <Link href="/atlas">BZA Atlas</Link>
      <Link href="/graphics/bza/" aria-current={current === 'bza-graphics' ? 'page' : undefined}>Create a graphic</Link>
      {entries.map((entry) => {
        const active = entry.slug === current;
        return (
          <Link
            key={entry.slug}
            href={`/publications/${entry.slug}`}
            className={active ? "active" : undefined}
            aria-current={active ? "page" : undefined}
          >
            {entry.navLabel}
          </Link>
        );
      })}
      <Link href="/#about">About</Link>
    </nav>
  );
}
