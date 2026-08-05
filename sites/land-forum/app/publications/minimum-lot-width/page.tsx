import rules from "../../../public/data/zoning/parcel-rules.json";
import type { ParcelRuleSummary } from "../../../lib/atlas/specs/parcel-rule";
import { LOT_WIDTH } from "../../../lib/atlas/specs/rules";
import ParcelRulePage, {
  parcelRuleMetadata,
} from "../../../components/ParcelRulePage";

const summary = rules.lot_width as ParcelRuleSummary;

export const metadata = parcelRuleMetadata(LOT_WIDTH, summary);

export default function Page() {
  return <ParcelRulePage config={LOT_WIDTH} summary={summary} />;
}
