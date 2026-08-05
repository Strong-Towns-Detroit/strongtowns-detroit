import type { Metadata } from "next";
import { Suspense } from "react";
import rules from "../../../../public/data/zoning/parcel-rules.json";
import type { QuantitySummary } from "../../../../lib/atlas/specs/quantity";
import { ASSESSED_VALUE_PER_ACRE } from "../../../../lib/atlas/specs/quantities";
import QuantityPoster from "../../../../components/QuantityPoster";

const summary = rules.assessed_value_per_acre as QuantitySummary;

export const metadata: Metadata = {
  title: `${ASSESSED_VALUE_PER_ACRE.title} — board`,
  robots: { index: false, follow: false },
};

export default function PosterPage() {
  return (
    <main id="main" className="poster-host">
      <Suspense fallback={null}>
        <QuantityPoster config={ASSESSED_VALUE_PER_ACRE} summary={summary} />
      </Suspense>
    </main>
  );
}
