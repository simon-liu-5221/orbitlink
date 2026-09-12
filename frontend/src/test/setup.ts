import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement ResizeObserver; Recharts' ResponsiveContainer needs
// one to exist, even though layout-observing is meaningless without a real
// viewport (PR-13).
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom never runs real layout, so every element's getBoundingClientRect is
// 0x0 by default. ResponsiveContainer reads it to size the chart and, at
// 0x0, refuses to render anything inside it. A fixed non-zero size is enough
// for Recharts to mount its children so tests can assert on rendered content.
HTMLElement.prototype.getBoundingClientRect = () => ({
  width: 400,
  height: 300,
  top: 0,
  left: 0,
  right: 400,
  bottom: 300,
  x: 0,
  y: 0,
  toJSON() {},
});
