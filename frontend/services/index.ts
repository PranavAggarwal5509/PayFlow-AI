import { get, getPage, send, uploadFile } from "@/lib/api";
import type {
  ActivityItem,
  AppSettings,
  DashboardStats,
  InvoiceDetail,
  InvoiceListItem,
  OperationalMetrics,
  Paginated,
  PurchaseOrder,
  PurchaseOrderDetail,
  Review,
  ReviewAction,
  ReviewListItem,
  RunDetail,
  RunSummary,
  UploadResult,
  Vendor,
} from "@/types/api";

type Params = Record<string, string | number | undefined>;

export const invoiceService = {
  list: (params: Params): Promise<Paginated<InvoiceListItem>> => getPage("/invoices", params),
  get: (id: string): Promise<InvoiceDetail> => get(`/invoices/${id}`),
  upload: (file: File, onProgress: (percent: number) => void): Promise<UploadResult> =>
    uploadFile("/invoices/upload", file, onProgress),
  retry: (id: string): Promise<UploadResult> => send("POST", `/invoices/${id}/retry`),
};

export const runService = {
  list: (params: Params): Promise<Paginated<RunSummary>> => getPage("/runs", params),
  get: (id: string): Promise<RunDetail> => get(`/runs/${id}`),
};

export const dashboardService = {
  stats: (days = 30): Promise<DashboardStats> => get("/dashboard/stats", { days }),
  developerAnalytics: (days = 30): Promise<OperationalMetrics> =>
    get("/dashboard/developer-analytics", { days }),
  activity: (limit = 8): Promise<ActivityItem[]> => get("/dashboard/recent-activity", { limit }),
};

export interface VendorInput {
  vendor_name: string;
  gstin?: string | null;
  address?: string | null;
  email?: string | null;
  phone?: string | null;
  status: string;
}

export const vendorService = {
  list: (params: Params): Promise<Paginated<Vendor>> => getPage("/vendors", params),
  get: (id: string): Promise<Vendor> => get(`/vendors/${id}`),
  create: (body: VendorInput): Promise<Vendor> => send("POST", "/vendors", body),
  update: (id: string, body: Partial<VendorInput>): Promise<Vendor> => send("PATCH", `/vendors/${id}`, body),
};

export const purchaseOrderService = {
  list: (params: Params): Promise<Paginated<PurchaseOrder>> => getPage("/purchase-orders", params),
  get: (id: string): Promise<PurchaseOrderDetail> => get(`/purchase-orders/${id}`),
};

export const reviewService = {
  list: (params: Params): Promise<Paginated<ReviewListItem>> => getPage("/reviews", params),
  decide: (id: string, action: ReviewAction, comment: string): Promise<Review> =>
    send("POST", `/reviews/${id}/decision`, { action, comment }),
};

export const settingsService = {
  get: (): Promise<AppSettings> => get("/settings"),
};


export interface RoleInfo {
  role: string;
  label: string;
  summary: string;
  permissions: string[];
}

export interface DemoAccount {
  email: string;
  name: string;
  role: string;
  password: string;
}

export const authService = {
  login: (email: string, password: string, remember: boolean) =>
    send<{ token: string; expires_at: number; user: import("@/lib/session").SessionUser }>("POST", "/auth/login", {
      email,
      password,
      remember,
    }),
  me: () => get<import("@/lib/session").SessionUser>("/auth/me"),
  logout: () => send<{ ok: boolean }>("POST", "/auth/logout"),
  roles: () => get<{ permissions: string[]; roles: RoleInfo[]; demo_accounts: DemoAccount[] }>("/auth/roles"),
};

export interface ResetSummary {
  invoices: number;
  runs: number;
  reviews: number;
  decisions: number;
  checks: number;
  po_allocations: number;
  email_drafts: number;
  audit_entries: number;
  files: number;
  seeded_invoices_kept: number;
}

export const demoService = {
  preview: () => get<ResetSummary>("/demo/reset"),
  reset: () => send<ResetSummary>("POST", "/demo/reset"),
};
