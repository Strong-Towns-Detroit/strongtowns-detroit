import { Suspense } from "react";
import rules from "../../../../public/data/zoning/parcel-rules.json";
import type { ParcelRuleSummary } from "../../../../lib/atlas/specs/parcel-rule";
import { SETBACK_ENVELOPE } from "../../../../lib/atlas/specs/rules";
import { posterMetadata } from "../../../../components/ParcelRulePage";
import ParcelRulePoster from "../../../../components/ParcelRulePoster";

const summary = rules.setback_envelope as ParcelRuleSummary;

export const metadata = posterMetadata(SETBACK_ENVELOPE);

export default function PosterPage() {
  return (
    <main id="main" className="poster-host">
      <Suspense fallback={null}>
        <ParcelRulePoster config={SETBACK_ENVELOPE} summary={summary} />
      </Suspense>
    </main>
  );
}
