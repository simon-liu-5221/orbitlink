/**
 * The "Export report (PDF)" button (spec PR-11). html2canvas and jsPDF are
 * both sizeable — they're dynamically imported here, on click, rather than
 * bundled with the result page (AC-6, PERF-05).
 */

export interface ReportSection {
  label: string;
  /** The DOM node to screenshot. Skipped (with a console warning) if null —
   * e.g. a section that hasn't rendered yet. */
  element: HTMLElement | null;
}

const PAGE_MARGIN_PT = 24;

export async function buildPdfReport(
  sections: ReportSection[],
  filename: string,
): Promise<void> {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import("html2canvas"),
    import("jspdf"),
  ]);

  const pdf = new jsPDF({ unit: "pt", format: "a4" });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const usableWidth = pageWidth - PAGE_MARGIN_PT * 2;
  const usableHeight = pageHeight - PAGE_MARGIN_PT * 2;

  let addedAnyPage = false;

  for (const section of sections) {
    if (!section.element) {
      console.warn(`PDF export: skipping "${section.label}" — not rendered`);
      continue;
    }

    const canvas = await html2canvas(section.element, {
      scale: 2,
      backgroundColor: "#ffffff",
    });
    const imageData = canvas.toDataURL("image/png");
    const imageWidth = usableWidth;
    const imageHeight = (canvas.height * imageWidth) / canvas.width;

    if (addedAnyPage) pdf.addPage();
    pdf.addImage(
      imageData,
      "PNG",
      PAGE_MARGIN_PT,
      PAGE_MARGIN_PT,
      imageWidth,
      Math.min(imageHeight, usableHeight),
    );
    addedAnyPage = true;
  }

  pdf.save(filename);
}
