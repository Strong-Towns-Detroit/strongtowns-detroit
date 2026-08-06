import rules from "../../../public/data/zoning/parcel-rules.json";
import type { QuantitySummary } from "../../../lib/atlas/specs/quantity";
import { ASSESSED_VALUE_PER_ACRE } from "../../../lib/atlas/specs/quantities";
import QuantityPage, { quantityMetadata } from "../../../components/QuantityPage";

const summary = rules.assessed_value_per_acre as QuantitySummary;

export const metadata = quantityMetadata(ASSESSED_VALUE_PER_ACRE, summary);

export default function Page() {
  return <QuantityPage config={ASSESSED_VALUE_PER_ACRE} summary={summary} />;
}
