import { describe, expect, it } from "vitest";
import { fmtPct, fmtQty, fmtTs, fmtUsd } from "./api";

describe("fmtUsd", () => {
  it("formats dollars with two decimals", () => {
    expect(fmtUsd(1234.5)).toBe("$1,234.50");
    expect(fmtUsd(0)).toBe("$0.00");
  });
  it("renders em-dash for null or undefined", () => {
    expect(fmtUsd(null)).toBe("—");
    expect(fmtUsd(undefined)).toBe("—");
  });
});

describe("fmtPct", () => {
  it("adds sign and rounds to two decimals", () => {
    expect(fmtPct(1.234)).toBe("+1.23%");
    expect(fmtPct(-0.5)).toBe("-0.50%");
    expect(fmtPct(0)).toBe("+0.00%");
  });
});

describe("fmtQty", () => {
  it("keeps up to four significant decimals", () => {
    expect(fmtQty(0.04)).toBe("0.04");
    expect(fmtQty(1)).toBe("1");
  });
});

describe("fmtTs", () => {
  it("renders em-dash for null or zero", () => {
    expect(fmtTs(null)).toBe("—");
    expect(fmtTs(0)).toBe("—");
  });
});