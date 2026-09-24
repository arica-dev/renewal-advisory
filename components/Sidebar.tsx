"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./Icon";

const NAV: { href: string; label: string; icon: IconName; match: (p: string) => boolean; badge?: string }[] = [
  { href: "/", label: "Renewals", icon: "renew", match: (p) => p === "/" || (p.startsWith("/groups") && !p.endsWith("/brief")), badge: "3" },
  { href: "/filings", label: "Rate filings", icon: "chart", match: (p) => p.startsWith("/filings") },
  { href: "/groups/grp_30_2/brief", label: "Briefs", icon: "doc", match: (p) => p.endsWith("/brief") },
];

export function Logo() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <rect width="28" height="28" rx="8" fill="#1F3D2C" />
      <path d="M8 18.5 12.5 14l3 3L20 10.5" stroke="#D0FAE2" strokeWidth="2.2" fill="none"
        strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Sidebar() {
  const pathname = usePathname() ?? "/";
  return (
    <nav aria-label="Main"
      className="sticky top-0 hidden h-screen w-[232px] shrink-0 flex-col justify-between border-r border-line bg-surface px-4 py-6 md:flex">
      <div className="flex flex-col gap-7">
        <Link href="/" className="flex items-center gap-2.5 px-2 text-ink no-underline">
          <Logo />
          <span className="text-base font-semibold tracking-tight">Renewal Advisor</span>
        </Link>
        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <li key={item.label}>
                <Link href={item.href} aria-current={active ? "page" : undefined}
                  className={`flex min-h-11 items-center gap-2.5 rounded-[10px] px-3 text-sm no-underline transition-colors ${
                    active ? "bg-mint-soft font-semibold text-ink" : "text-ink-2 hover:bg-tint hover:text-ink"}`}>
                  <Icon name={item.icon} className={active ? "text-green" : "text-ink-2"} />
                  <span className="flex-1">{item.label}</span>
                  {item.badge && (
                    <span className={`num rounded-full px-2 text-xs ${active ? "bg-green text-white" : "bg-line text-ink"}`}>
                      {item.badge}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="flex items-center gap-2.5 border-t border-line px-2 pt-3">
        <div className="flex size-8 items-center justify-center rounded-full bg-mint text-[11px] font-bold text-deep">BN</div>
        <div className="flex flex-col">
          <span className="text-[13px] font-semibold">[Broker name]</span>
          <span className="text-xs text-ink-3">[Agency]</span>
        </div>
      </div>
    </nav>
  );
}
