export class ApiClientError extends Error {
  constructor(public readonly code: string, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  const payload = await response.json();
  if (!response.ok) {
    throw new ApiClientError(payload.code ?? "REQUEST_FAILED", payload.message ?? "请求失败");
  }
  return payload as T;
}

