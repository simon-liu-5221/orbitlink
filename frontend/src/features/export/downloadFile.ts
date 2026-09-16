/** Trigger a browser download for in-memory content — no server round trip. */

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function downloadText(
  text: string,
  filename: string,
  mimeType: string,
): void {
  downloadBlob(new Blob([text], { type: mimeType }), filename);
}
