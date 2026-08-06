# Parking land-consumption companion

This exhibit translates the 1,075-space requested gap in the numeric BZA
parking corpus into an equivalent conventional surface-parking footprint.

It is not a claim that this land was actually paved. Most cases received
relief, and the applicants came to the BZA precisely because they did not
propose all the spaces in the requirement.

## Assumption

The public graphic uses 300–350 square feet per surface space, including the
stall's share of aisles and circulation:

- The U.S. Environmental Protection Agency reports a range of 250–400 square
  feet per residential surface-parking space and an average near 350.
- An American Planning Association design reference uses 300 square feet per
  space including aisles, entrances, exits, and landscaping.

Sources:

- https://nepis.epa.gov/Exe/ZyPURL.cgi?Dockey=9101SP2T.TXT
- https://www.planning.org/pas/reports/report59.htm

The output sensitivity table also reports 250, 325, and 400 square-foot
scenarios. One acre equals 43,560 square feet.

Run:

```bash
python projects/detroit-land-use-forum/parking-land-consumption/build_parking_land_asset.py
```
