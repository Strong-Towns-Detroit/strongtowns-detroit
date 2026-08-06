# BZA intake dates

`case_histories.csv` records the first observed hearing, not when an appeal or
variance application entered the BZA process. Measuring the complete process
requires an intake date.

## Preferred source

Detroit's BZA rules require the director to maintain a docket containing the
application history, hearing activity, notices, postponements, and final
disposition. The official appeal form also contains dated applicant, BSEED, and
BZA staff signature fields. A docket export is therefore the authoritative
source.

Detroit uses eLAPS, backed by Accela, for planning records. Accela exposes
`openedDate`, the date its application record was opened. This is a useful
candidate intake date, but only after matching the Accela record to the BZA case.
It may differ from the applicant's signature date, BSEED receipt date, or the
date a complete application was accepted.

## Accela candidate pass

Run a one-case smoke test:

```sh
python pipelines/zoning/enrich_bza_intake_dates.py --case-limit 1
```

Then run the complete pass:

```sh
python pipelines/zoning/enrich_bza_intake_dates.py
```

Responses are cached under `bza_dataset_gemini/accela_raw/`. Candidate matches
are written to `bza_dataset_gemini/intake_date_candidates.csv`.

The script does not silently assign intake dates. It scores address agreement,
BZA case-number evidence, and whether the Accela record type identifies a zoning
appeal. `strong_candidate` still requires review before publication. A matching
address alone is insufficient because one site can have many unrelated permits.

Despite Accela calling this endpoint “No authorization required,” anonymous
requests still require `x-accela-appid`, `x-accela-agency`, and
`x-accela-environment`. Put the citizen-app ID in `ACCELA_APP_ID` in `.env`.
Alternatively, authenticated requests can use `ACCELA_ACCESS_TOKEN`. Do not
commit either credential.

## Authoritative-data request

Request an electronic export of the BZA docket for the study period with:

- BZA case number
- application received/filed date
- BSEED receipt or referral date, where applicable
- BZA staff acceptance/completeness date
- property address and parcel
- scheduled and actual hearing dates
- postponements and rehearings
- final disposition and disposition date

Keep each date field separately. Do not collapse them into one generic
“application date”; the distinctions determine whether we are measuring
applicant preparation, agency intake, completeness review, scheduling, or Board
deliberation.

## Public eLAPS investigation (2026-07-28)

The normal Planning search URL redirects anonymous visitors to Accela login.
Adding `isToShowInspection=yes` reaches the public search form:

```text
https://aca-prod.accela.com/DETROIT/Cap/CapHome.aspx?isToShowInspection=yes&TabName=Planning&module=Planning
```

The public form was inspected in a real browser through Playwright. It exposes
record number, entered-date range, address, and parcel fields. Its Planning
record-type selector did not expose any record types.

Two controlled searches were run against recent case `BZA2025-00049`, first by
its exact printed record number and then by its minutes address, `2971
BELLEVUE`. Both returned no records. Searching the Permits module by the exact
BZA number also returned no records. The minutes identify the underlying BSEED
record as `SLU2023-00118`; an exact Planning search for that record likewise
returned no records. A historical address search generated Accela's generic
server-error page.

The public portal's OAuth redirect exposed its client identifier. Using that
identifier with the anonymous Construct headers reached Detroit's tenant, but
both the address query and a minimal Planning/date query returned HTTP 500.
This does not establish that no underlying permit records are public. It does
show that the BZA docket itself is not discoverable through the tested anonymous
Planning and Permits searches.

Do not build a large browser scraper until one known BZA record can be retrieved
manually. The next authoritative route is the docket export request. The
developer-app API route can be retested when Accela approves the account.
