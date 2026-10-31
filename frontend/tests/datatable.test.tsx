import type { ColumnDef } from "@tanstack/react-table";
import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { DataTable } from "@/components/tables/data-table";

interface TestRow {
  id: string;
  name: string;
  amount: string;
}

const columns: ColumnDef<TestRow, unknown>[] = [
  { id: "name", header: "Vendor Name", accessorKey: "name" },
  { id: "amount", header: "Amount", accessorKey: "amount" },
];

const mockData: TestRow[] = [
  { id: "1", name: "Acme Industrial Supplies", amount: "₹45,000" },
  { id: "2", name: "Global Cloud Tech", amount: "₹12,400" },
];

describe("DataTable Component", () => {
  it("renders data rows and column headers accurately", () => {
    render(
      <DataTable
        columns={columns}
        data={mockData}
        loading={false}
        error={null}
        meta={{ page: 1, page_size: 10, total: 2, total_pages: 1 }}
      />,
    );

    expect(screen.getByText("Vendor Name")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
    expect(screen.getByText("Acme Industrial Supplies")).toBeInTheDocument();
    expect(screen.getByText("Global Cloud Tech")).toBeInTheDocument();
  });

  it("renders loading skeleton when loading is true", () => {
    const { container } = render(
      <DataTable
        columns={columns}
        data={[]}
        loading={true}
        error={null}
      />,
    );

    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders empty state when data is empty and not loading", () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        loading={false}
        error={null}
        emptyTitle="No invoices found"
        emptyDescription="Try uploading an invoice."
      />,
    );

    expect(screen.getByText("No invoices found")).toBeInTheDocument();
    expect(screen.getByText("Try uploading an invoice.")).toBeInTheDocument();
  });

  it("renders error state when error is provided", () => {
    render(
      <DataTable
        columns={columns}
        data={[]}
        loading={false}
        error="Network timeout connecting to backend."
      />,
    );

    expect(screen.getByText("Network timeout connecting to backend.")).toBeInTheDocument();
  });
});

