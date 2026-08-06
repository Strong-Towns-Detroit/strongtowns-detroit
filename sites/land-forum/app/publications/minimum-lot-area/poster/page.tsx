import { Suspense } from "react";
import rules from "../../../../public/data/zoning/parcel-rules.json";
import type { ParcelRuleSummary } from "../../../../lib/atlas/specs/parcel-rule";
import { LOT_AREA } from "../../../../lib/atlas/specs/rules";
import { posterMetadata } from "../../../../components/ParcelRulePage";
import ParcelRulePoster from "../../../../components/ParcelRulePoster";

const summary = rules.lot_area as ParcelRuleSummary;

export const metadata = posterMetadata(LOT_AREA);

export default function PosterPage() {
  return (
    <main id="main" className="poster-host">
      <Suspense fallback={null}>
        <ParcelRulePoster config={LOT_AREA} summary={summary} />
      </Suspense>
    </main>
  );
}
