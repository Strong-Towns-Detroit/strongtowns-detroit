import rules from "../../../public/data/zoning/parcel-rules.json";
import type { ParcelRuleSummary } from "../../../lib/atlas/specs/parcel-rule";
import { LOT_AREA } from "../../../lib/atlas/specs/rules";
import ParcelRulePage, {
  parcelRuleMetadata,
} from "../../../components/ParcelRulePage";

const summary = rules.lot_area as ParcelRuleSummary;

export const metadata = parcelRuleMetadata(LOT_AREA, summary);

export default function Page() {
  return <ParcelRulePage config={LOT_AREA} summary={summary} />;
}
