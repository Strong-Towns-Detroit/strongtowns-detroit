import type { MetadataRoute } from "next";
import { absoluteUrl } from "./site";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // Generated map payloads and the mirrored source PDFs are linked from
        // the atlas, but they are not pages and should not compete with it in
        // search results.
        disallow: ["/data/", "/bza-minutes/"],
      },
    ],
    sitemap: absoluteUrl("/sitemap.xml"),
    host: absoluteUrl("/"),
  };
}
