import type { MetadataRoute } from "next";
import { absoluteUrl, routes } from "./site";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  // Static export, so this is the build time. Good enough as a "last known
  // good" signal, and it beats omitting the field.
  const lastModified = new Date();

  return routes.map((route) => ({
    url: absoluteUrl(route.path),
    lastModified,
    changeFrequency: route.changeFrequency,
    priority: route.priority,
  }));
}
