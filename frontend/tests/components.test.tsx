import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";

import { DecisionBadge } from "@/components/invoices/status-badges";
import { PageHeader } from "@/components/layout/page-header";

describe("PageHeader Component", () => {
  it("renders title, description, and action buttons properly", () => {
    render(
      <PageHeader
        title="Purchase Orders"
        description="Manage purchase orders and balances."
        actions={<button data-testid="action-btn">New Order</button>}
      />,
    );

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Purchase Orders");
    expect(screen.getByText("Manage purchase orders and balances.")).toBeInTheDocument();
    expect(screen.getByTestId("action-btn")).toHaveTextContent("New Order");
  });
});

describe("DecisionBadge Component", () => {
  it("renders Approved with green success styling", () => {
    render(<DecisionBadge status="APPROVED" />);
    const badge = screen.getByText("Approved");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("text-success");
  });

  it("renders Needs Review with amber warning styling", () => {
    render(<DecisionBadge status="NEEDS_REVIEW" />);
    const badge = screen.getByText("Needs review");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("text-warning");
  });

  it("renders Rejected with rose danger styling", () => {
    render(<DecisionBadge status="REJECTED" />);
    const badge = screen.getByText("Rejected");
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain("text-danger");
  });

  it("renders dash for null status", () => {
    render(<DecisionBadge status={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
