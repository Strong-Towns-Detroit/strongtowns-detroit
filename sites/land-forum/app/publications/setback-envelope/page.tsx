import rules from "../../../public/data/zoning/parcel-rules.json";
import type { ParcelRuleSummary } from "../../../lib/atlas/specs/parcel-rule";
import { SETBACK_ENVELOPE } from "../../../lib/atlas/specs/rules";
import ParcelRulePage, {
  parcelRuleMetadata,
} from "../../../components/ParcelRulePage";

const summary = rules.setback_envelope as ParcelRuleSummary;

export const metadata = parcelRuleMetadata(SETBACK_ENVELOPE, summary);

export default function Page() {
  return <ParcelRulePage config={SETBACK_ENVELOPE} summary={summary} />;
}
