const BASE = "/api/v1";

export interface TokenData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserData {
  id: string;
  email: string;
  created_at: string;
}

export interface JobData {
  id: string;
  status: string;
  celery_task_id: string | null;
  minio_object_key: string | null;
  download_url: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginationMeta {
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface ApiError {
  error: { code: string; message: string };
}

class ApiRequestError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

async function rawRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });

  const body: unknown = await res.json();

  if (!res.ok) {
    const err = body as ApiError;
    throw new ApiRequestError(
      err.error.code,
      err.error.message,
      res.status,
    );
  }

  return body as T;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const body = await rawRequest<{ data: T }>(path, options);
  return body.data;
}

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

export async function register(
  email: string,
  password: string,
): Promise<UserData> {
  return request<UserData>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string,
): Promise<TokenData> {
  return request<TokenData>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function refreshToken(
  refresh: string,
): Promise<TokenData> {
  return request<TokenData>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refresh }),
  });
}

export async function fetchMe(token: string): Promise<UserData> {
  return request<UserData>("/auth/me", {
    headers: authHeaders(token),
  });
}

export async function createJob(token: string): Promise<JobData> {
  return request<JobData>("/jobs", {
    method: "POST",
    headers: authHeaders(token),
  });
}

export async function listJobs(
  token: string,
  page: number = 1,
  perPage: number = 20,
): Promise<{ data: JobData[]; meta: PaginationMeta }> {
  return rawRequest<{ data: JobData[]; meta: PaginationMeta }>(
    `/jobs?page=${page}&per_page=${perPage}`,
    { headers: authHeaders(token) },
  );
}

export async function getJob(
  token: string,
  jobId: string,
): Promise<JobData> {
  return request<JobData>(`/jobs/${jobId}`, {
    headers: authHeaders(token),
  });
}

export async function cancelJob(
  token: string,
  jobId: string,
): Promise<JobData> {
  return request<JobData>(`/jobs/${jobId}/cancel`, {
    method: "POST",
    headers: authHeaders(token),
  });
}

export function sseUrl(jobId: string, token: string): string {
  return `${BASE}/jobs/${jobId}/events?token=${token}`;
}

export { ApiRequestError };
