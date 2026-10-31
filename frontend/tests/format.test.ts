import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatDate,
  formatDateTime,
  formatDuration,
  formatMoney,
  titleCase,
} from "@/lib/format";

describe("formatMoney", () => {
  it("formats standard amounts in INR", () => {
    const formatted = formatMoney("12500.50", "INR");
    expect(formatted).toContain("12,500.50");
  });

  it("formats foreign currency amounts like USD and EUR", () => {
    const usd = formatMoney("4500.00", "USD");
    expect(usd).toContain("4,500.00");

    const eur = formatMoney("3200.75", "EUR");
    expect(eur).toContain("3.200,75");
  });

  it("handles null, empty, or invalid numeric inputs gracefully", () => {
    expect(formatMoney(null)).toBe("—");
    expect(formatMoney(undefined)).toBe("—");
    expect(formatMoney("")).toBe("—");
    expect(formatMoney("invalid_number")).toBe("—");
  });
});

describe("formatDate and formatDateTime", () => {
  it("formats ISO date string into readable day, month, year", () => {
    const formatted = formatDate("2026-10-15");
    expect(formatted).toMatch(/15\s+Oct\s+2026/);
  });

  it("formats ISO datetime string", () => {
    const formatted = formatDateTime("2026-10-15T14:30:00Z");
    expect(formatted).toMatch(/15\s+Oct/);
  });

  it("returns dash for invalid or empty dates", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("not-a-date")).toBe("—");
    expect(formatDateTime(undefined)).toBe("—");
  });
});

describe("formatDuration", () => {
  it("formats durations less than 1 second", () => {
    expect(formatDuration(0.4)).toBe("<1s");
  });

  it("formats durations under a minute", () => {
    expect(formatDuration(45.2)).toBe("45s");
  });

  it("formats multi-minute durations", () => {
    expect(formatDuration(125)).toBe("2m 5s");
  });

  it("returns dash when seconds are null or undefined", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });
});

describe("formatBytes", () => {
  it("formats bytes, kilobytes, and megabytes", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5242880)).toBe("5.0 MB");
  });
});

describe("titleCase", () => {
  it("transforms snake_case and UPPERCASE strings to Title Case", () => {
    expect(titleCase("NEEDS_REVIEW")).toBe("Needs Review");
    expect(titleCase("APPROVED")).toBe("Approved");
    expect(titleCase("po_matching")).toBe("Po Matching");
  });
});

