import type { Metadata } from "next";
import "leaflet/dist/leaflet.css";
import "./styles.css";

export const metadata: Metadata = {
  title: "Land Forum — Detroit",
  description:
    "Public evidence and open inquiry about how Detroit uses its land.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
