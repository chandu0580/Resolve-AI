/** Safe runtime facts shown in the shell (from /api/v1/config and /api/v1/health; no secrets, no endpoint URLs). */
export interface RuntimeInfo {
  env: string | null;
  model: string | null;
  provider: string | null;
  llmEnabled: boolean | null;
  apiVersion: string | null;
  apiReachable: boolean;
}
