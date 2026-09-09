# Browser renderer distribution

The canonical renderer lives in the sibling `strongtowns-graphics/browser`
package. This directory contains its versioned npm distribution, consumed by
the Land Forum site's lockfile. Vendoring the small package lets standalone
consumer checkouts and CI build without an unpublished registry dependency or
an unpinned sibling checkout.

To update it, change the source package, run its tests, increment its version,
then run `npm pack --pack-destination /tmp` from that package. Copy the resulting
archive here and update the site's `@strongtowns/graphics-browser` file dependency
and npm lockfile. Run the website's unit and browser tests and inspect exports.
Do not edit the tarball. The npm lockfile records its integrity hash.

The initial 0.1.0 distribution is introduced together with the source package;
it requires no Python SDK or CLI migration.
