# NEZ-NR as a path toward land-value taxation

Status: initial legal and data audit, July 30, 2026. This is policy research,
not legal advice.

## Short answer

Detroit's Neighborhood Enterprise Zone program for new and rehabilitated
facilities (NEZ-NR) is **DALT-like, but it is not DALT**.

- Land remains on the ordinary ad valorem roll and is taxed at the full
  applicable millage.
- The certified building is removed from the ordinary roll and placed on an
  NEZ specific-tax roll.
- The building retains an assessed/taxable value. The program changes the tax
  applied to that value; it does not erase the improvement assessment.
- For a post-2005 **new-facility** certificate, the building tax is generally
  one-half of the applicable preceding-year statewide average millage until
  the phase-out years. The 2026 rate is 17.550 mills for PRE facilities and
  27.070 mills for non-PRE facilities.
- For a post-2005 **rehabilitated-facility** certificate, ordinary millage is
  applied to the building's taxable value from immediately before the
  certificate became effective. In practical terms, the improvement tax base
  is frozen before the rehabilitation rather than taxed at the new-facility
  rate.
- Certificates generally last 6–15 years. The last three years phase the
  facility back toward ordinary taxation.

DALT, as proposed by Lars Doucet, fully exempts new improvement value during
the initial abatement. NEZ-NR instead taxes improvements at a preferential
specific-tax rate. Both preserve full-rate land taxation and reduce the
penalty on construction.

## What Detroit can do without Lansing

Under the existing state act, Detroit can:

1. Designate or amend eligible NEZ-NR district boundaries by City Council
   resolution, subject to the act's eligibility, contiguity, and acreage
   restrictions.
2. Approve or deny individual applications locally before State Tax Commission
   review.
3. Choose certificate terms within the statutory range, generally 6–15 years.
4. Standardize a local policy that favors the longest permissible term and
   broad, predictable access for qualifying residential projects.
5. Publish the land and improvement portions separately and make the
   land-at-full-rate / building-at-reduced-rate structure legible.

Detroit cannot, by ordinance alone:

1. Change the statutory NEZ specific-tax formula.
2. turn the reduced improvement tax into a universal zero-rate building
   exemption;
3. remove the residential, facility, district, or certificate eligibility
   rules;
4. eliminate State Tax Commission involvement; or
5. make a citywide pure land-value tax under the NEZ statute.

Accordingly, Detroit can make NEZ-NR more systematic and more DALT-like without
new state legislation, but a universal or pure LVT still appears to require a
state-law change.

## Data already present locally

The City parcel file contains:

- 5,879 records coded `NEZ LAND`;
- 14 records coded `NEZ BLDG`;
- a `related_parcel_id` on the NEZ land records that appears to point to the
  associated special-roll building account; and
- current assessed and taxable values for the land accounts.

The associated 27-series building accounts are not present in the downloaded
general parcel layer. Consequently, the current parcel file cannot by itself
measure the improvement tax base, NEZ savings, or a DALT counterfactual.

## Analysis to build

### 1. Assemble the active certificate universe

- Download current and historical State Tax Commission NEZ certificate
  records.
- Restrict to City of Detroit.
- Separate new, rehabilitated, and homestead certificates.
- Match certificate number, owner, address, effective date, expiration date,
  and facility type to City parcel identifiers.

### 2. Obtain the missing special-roll values

Request or locate Detroit's current NEZ specific-tax roll with:

- special-roll account / 27-series identifier;
- linked land parcel;
- facility assessed value;
- facility taxable value;
- PRE status;
- certificate number and type;
- effective and expiration years; and
- current specific-tax rate and tax billed.

The annual report required by MCL 207.786 is another promising source because
it must include certificate activity and estimated tax savings.

### 3. Reconstruct four tax scenarios

For each active certificate:

1. ordinary ad valorem property tax;
2. actual NEZ-NR specific tax;
3. full ten-year DALT improvement exemption, with land unchanged; and
4. a revenue-neutral DALT or split-rate alternative.

Keep assessed value, state equalized value, taxable value, millage, and actual
tax billed separate throughout.

### 4. Report policy-relevant results

- annual improvement-tax reduction under NEZ-NR;
- land's share of the remaining bill;
- construction and rehabilitation by certificate cohort;
- geographic distribution and neighborhood concentration;
- certificates nearing phase-out;
- revenue change under DALT and revenue-neutral rates; and
- distribution by housing type, ownership, PRE status, and project scale.

## Primary authorities

- Neighborhood Enterprise Zone Act, 1992 PA 147, MCL 207.771–207.786.
- Michigan Department of Treasury, Neighborhood Enterprise Zone FAQ.
- Michigan Department of Treasury, 2026 New Facility NEZ Tax Rates.
- City of Detroit, NEZ-NR district data and program materials.
