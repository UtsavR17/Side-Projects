import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import LiveUpdates from "@/components/LiveUpdates";

export const metadata: Metadata = {
  title: "FormEdge — Racing Intelligence",
  description: "Horse racing prediction & analytics (MTC Mauritius)",
};

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/races", label: "Races" },
  { href: "/horses", label: "Horses" },
  { href: "/accuracy", label: "Accuracy" },
  { href: "/leaderboard", label: "Models" },
  { href: "/simulator", label: "Simulator" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <Link href="/" className="brand">
            Form<span>Edge</span>
          </Link>
          <nav className="nav">
            {NAV.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="container">{children}</main>
        <footer className="footer">
          FormEdge — predictions are pre-computed by the background pipeline. Not betting
          advice.
        </footer>
        <LiveUpdates />
      </body>
    </html>
  );
}
