import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { buildPdfReport } from "./pdfReport";
import type { ReportSection } from "./pdfReport";

const calls: string[] = [];

const fakeCanvas = {
  width: 800,
  height: 600,
  toDataURL: () => "data:image/png;base64,fake",
};

const html2canvasMock = vi.fn(async (el: HTMLElement) => {
  calls.push(`capture:${el.dataset.section}`);
  return fakeCanvas as unknown as HTMLCanvasElement;
});

const pdfInstance = {
  internal: { pageSize: { getWidth: () => 595, getHeight: () => 842 } },
  addImage: vi.fn(() => calls.push("addImage")),
  addPage: vi.fn(() => calls.push("addPage")),
  save: vi.fn((filename: string) => calls.push(`save:${filename}`)),
};
const jsPDFMock = vi.fn((_options: unknown) => pdfInstance);

vi.mock("html2canvas", () => ({
  default: (el: HTMLElement) => html2canvasMock(el),
}));
vi.mock("jspdf", () => ({
  // must be a real constructor (not an arrow fn) — pdfReport.ts calls `new jsPDF(...)`
  jsPDF: function (this: unknown, options: unknown) {
    return jsPDFMock(options);
  },
}));

function elementLabeled(section: string): HTMLElement {
  const div = document.createElement("div");
  div.dataset.section = section;
  return div;
}

beforeEach(() => {
  calls.length = 0;
  html2canvasMock.mockClear();
  jsPDFMock.mockClear();
  pdfInstance.addImage.mockClear();
  pdfInstance.addPage.mockClear();
  pdfInstance.save.mockClear();
});
afterEach(() => vi.restoreAllMocks());

test("captures every section in order and adds a page between each (AC-5)", async () => {
  const sections: ReportSection[] = [
    { label: "Stats", element: elementLabeled("stats") },
    { label: "Graph", element: elementLabeled("graph") },
    { label: "Charts", element: elementLabeled("charts") },
  ];

  await buildPdfReport(sections, "report.pdf");

  expect(calls).toEqual([
    "capture:stats",
    "addImage",
    "capture:graph",
    "addPage",
    "addImage",
    "capture:charts",
    "addPage",
    "addImage",
    "save:report.pdf",
  ]);
});

test("a section with no rendered element yet is skipped, not captured as blank", async () => {
  const sections: ReportSection[] = [
    { label: "Stats", element: elementLabeled("stats") },
    { label: "Still loading", element: null },
  ];

  await buildPdfReport(sections, "report.pdf");

  expect(calls).toEqual(["capture:stats", "addImage", "save:report.pdf"]);
});

test("no page break before the very first captured section", async () => {
  await buildPdfReport(
    [{ label: "Only", element: elementLabeled("only") }],
    "r.pdf",
  );
  expect(pdfInstance.addPage).not.toHaveBeenCalled();
});
