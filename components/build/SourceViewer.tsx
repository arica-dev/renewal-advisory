"use client";

import { useEffect, useRef, useState } from "react";
import { usd, type Extraction, type Rate } from "@/lib/build";

const ZOOM = 2.2;
const VIEW_HEIGHT = 440;

/** Shows where a value came from: the PDF page with the value boxed, or the
 *  spreadsheet with the cell highlighted. */
export function SourceViewer({ result, rate, fallbackPage, fallbackSheet, flagged = false }:
  { result: Extraction; rate: Rate | null; fallbackPage: number; fallbackSheet?: string; flagged?: boolean }) {
  const cellRef = useRef<HTMLTableCellElement>(null);
  const frame = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);
  const [zoomed, setZoomed] = useState(true);
  const src = rate?.source;

  useEffect(() => {
    const el = frame.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(e!.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, [result.format]);

  useEffect(() => {
    cellRef.current?.scrollIntoView({ block: "center", inline: "nearest", behavior: "smooth" });
  }, [src?.sheet, src?.cell]);

  if (src?.edited && !src.page && !src.sheet) {
    return (
      <div className="flex min-h-48 items-center justify-center rounded-xl border border-dashed border-sage bg-tint p-6 text-center text-[13px] text-ink-2">
        Entered during review. This value isn&apos;t in the carrier&apos;s document.
      </div>
    );
  }

  if (result.format === "pdf") {
    const page = result.pages.find((p) => p.n === (src?.page ?? fallbackPage)) ?? result.pages[0];
    if (!page) return null;
    const box = src?.bbox && src.page === page.n ? src.bbox : null;
    const zoom = box && zoomed ? ZOOM : 1;
    const imgW = width * zoom;
    const imgH = imgW * (page.height / page.width);
    // Centre the boxed value in the frame, without scrolling past the page edges.
    let left = 0, top = 0;
    if (box && zoom > 1 && width) {
      const cx = ((box[0] + box[2]) / 2 / page.width) * imgW;
      const cy = ((box[1] + box[3]) / 2 / page.height) * imgH;
      left = Math.min(0, Math.max(width - imgW, width / 2 - cx));
      top = Math.min(0, Math.max(VIEW_HEIGHT - imgH, VIEW_HEIGHT / 2 - cy));
    }
    const tone = src?.edited || flagged || src?.verified === false ? "bg-amber/15 ring-amber" : "bg-green/15 ring-green";
    return (
      <figure className="m-0 flex flex-col gap-2">
        <div ref={frame} className="relative overflow-hidden rounded-xl border border-line bg-white"
          style={{ height: zoom > 1 ? VIEW_HEIGHT : width ? width * (page.height / page.width) : undefined }}>
          {width > 0 && (
            <div className="absolute transition-all duration-300 motion-reduce:transition-none" style={{ left, top, width: imgW, height: imgH }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={page.image} alt={`Page ${page.n} of ${result.filename}`} className="block h-full w-full" />
              {box && (
                <div aria-hidden="true" className={`absolute rounded-[3px] ring-2 ${tone}`}
                  style={{
                    left: `${(box[0] / page.width) * 100}%`, top: `${(box[1] / page.height) * 100}%`,
                    width: `${((box[2] - box[0]) / page.width) * 100}%`, height: `${((box[3] - box[1]) / page.height) * 100}%`,
                  }} />
              )}
            </div>
          )}
          {box && (
            <button type="button" onClick={() => setZoomed((z) => !z)}
              className="absolute right-2 top-2 rounded-full border border-line bg-surface/95 px-3 py-1 text-xs font-semibold text-ink-2 shadow-sm hover:text-ink">
              {zoomed ? "Whole page" : "Zoom in"}
            </button>
          )}
        </div>
        <figcaption className="text-xs text-ink-3">
          {result.filename} · page {page.n} of {result.pages.length}
          {src?.text && <> · printed <span className="num text-ink-2">{src.text}</span></>}
          {src?.edited && rate && <> · <span className="text-amber">corrected to <span className="num">{usd(rate.amount)}</span></span></>}
          {src?.verified === false && <span className="text-amber"> · not found on this page</span>}
          {!rate && " · select a rate to find it on the page"}
        </figcaption>
      </figure>
    );
  }

  const sheet = result.sheets.find((s) => s.name === (src?.sheet ?? fallbackSheet)) ?? result.sheets[0];
  if (!sheet) return null;
  const rows = sheet.rows.filter((r) => r.some((c) => c.value !== null));
  return (
    <figure className="m-0 flex flex-col gap-2">
      <div className="max-h-[520px] overflow-auto rounded-xl border border-line bg-white">
        <table className="w-full border-collapse text-[12px]">
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {row.slice(0, 6).map((c) => {
                  const on = c.cell === src?.cell && sheet.name === src?.sheet;
                  return (
                    <td key={c.cell} ref={on ? cellRef : undefined}
                      className={`max-w-[180px] truncate border border-line-2 px-2 py-1 ${on ? "bg-mint font-semibold text-deep ring-2 ring-inset ring-green" : "text-ink-2"}`}>
                      {c.value ?? ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <figcaption className="text-xs text-ink-3">
        {result.filename} · sheet &ldquo;{sheet.name}&rdquo;{src?.cell && sheet.name === src.sheet && <> · cell <span className="num">{src.cell}</span></>}
      </figcaption>
    </figure>
  );
}
