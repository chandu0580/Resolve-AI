/** User-facing explanations for API error codes: what happened and what the operator can do next. */
import type { ApiError } from "@/lib/api/client";

export interface ErrorExplanation {
  title: string;
  description: string;
  action: string;
}

const EXPLANATIONS: Record<string, ErrorExplanation> = {
  api_unavailable: {
    title: "ResolveAI API unavailable",
    description: "The console could not reach the FastAPI service.",
    action: "Start the backend with `python -m resolveai serve`, then reload this page.",
  },
  timeout: {
    title: "The agent did not answer in time",
    description: "Live model calls can take tens of seconds, but this request exceeded the console's limit.",
    action: "Retry. If it keeps happening, check the model endpoint or run the backend with RESOLVEAI_USE_LLM=false.",
  },
  agent_not_ready: {
    title: "Agent still loading",
    description: "The API is up, but the knowledge base, embeddings and classifier are still loading.",
    action: "Wait a few seconds and retry. The status indicator in the sidebar turns green when the agent is ready.",
  },
  agent_unavailable: {
    title: "Agent failed to load",
    description: "The API is running, but the agent could not start.",
    action: "Check the backend log and /api/v1/ready for the failing component.",
  },
  unauthorized: {
    title: "Not authorized",
    description: "The ResolveAI API requires credentials and the console's request was rejected.",
    action: "Set RESOLVEAI_API_TOKEN for the console server (it is never sent to the browser) and restart the console.",
  },
  forbidden: {
    title: "Access not permitted",
    description: "The console's credentials are valid but do not allow this operation (for example a read-only token trying to run the agent).",
    action: "Configure the console with a token that has the resolve scope.",
  },
  agent_busy: {
    title: "Agent busy",
    description: "The agent runs one conversation at a time and the waiting queue is full.",
    action: "Retry in a few seconds.",
  },
  rate_limited: {
    title: "Too many requests",
    description: "The API's per-client rate limit was reached.",
    action: "Wait for the time shown in the message, then retry.",
  },
  input_too_large: {
    title: "Conversation exceeds the configured limits",
    description: "Nothing was processed; limits are enforced before any model call.",
    action: "Shorten the message or remove earlier turns. The limits are shown on the configuration panel.",
  },
  validation_error: {
    title: "Request rejected by the API schema",
    description: "The request did not match the contract in docs/API.md.",
    action: "Check the fields listed in the details.",
  },
  invalid_conversation: {
    title: "The last turn must be the customer's",
    description: "ResolveAI handles the most recent customer message.",
    action: "Add or move the customer message to the end of the conversation.",
  },
  invalid_json: { title: "Invalid request body", description: "The API could not parse the request.", action: "Retry; if it persists, report the request id." },
  invalid_response: {
    title: "Unexpected response",
    description: "The API answered, but not with the JSON contract the console expects.",
    action: "Check that the backend version matches this console (see the version in the sidebar).",
  },
  trace_not_found: {
    title: "Trace not found",
    description: "No trace with this id exists in the API's trace store. Traces live in local files; a different trace directory or a cleaned store has no record of it.",
    action: "Open the Traces page to see the traces that exist.",
  },
  invalid_trace_id: { title: "Invalid trace id", description: "A trace id is 32 lowercase hexadecimal characters.", action: "Check the link or paste the full id." },
  evaluation_not_available: {
    title: "Evaluation results unavailable",
    description: "The frozen evaluation artifacts are missing from this checkout.",
    action: "Run `python scripts/evaluate.py --cached` in the repository.",
  },
  autonomy_invariant_violation: {
    title: "Automatic reply withheld",
    description: "The API's independent check found an automatic reply that did not satisfy the evidence invariant, so it was not returned.",
    action: "Open the trace for this request id and report it. This indicates a defect upstream of the API.",
  },
  internal_error: { title: "Unexpected server error", description: "The API failed without exposing details.", action: "Retry, and quote the request id when reporting it." },
  not_found: { title: "Not found", description: "The console or the API has no such endpoint or page.", action: "Check the link, or use the navigation." },
  method_not_allowed: { title: "Operation not allowed", description: "The API does not accept this method on this endpoint.", action: "Report the request id; the console should never send this." },
  auth_required: {
    title: "Not authorized",
    description: "The ResolveAI API requires credentials and the console's request carried none.",
    action: "Set RESOLVEAI_API_TOKEN for the console server (it is never sent to the browser) and restart the console.",
  },
  length_required: { title: "Request rejected", description: "The API requires a declared request size before it reads a body.", action: "Retry; if it persists, report the request id." },
  payload_too_large: {
    title: "Request too large",
    description: "The request body exceeded the API's size limit and was rejected before it was read.",
    action: "Shorten the conversation. The limits are listed on the Settings page.",
  },
  demo_not_available: { title: "Demo scenarios unavailable", description: "The API could not find its demo scenario file.", action: "Check that data/demo/scenarios.json exists in the backend checkout." },
  cancelled: { title: "Request cancelled", description: "The request was cancelled before the API answered. Nothing was recorded by the console.", action: "Run it again when ready." },
  http_error: { title: "Request failed", description: "The API answered with an unexpected status and no error details.", action: "Retry, and quote the request id if the problem persists." },
  client_error: { title: "Console error", description: "The console could not process the response.", action: "Reload the page. If it persists, report what you were doing." },
};

/** Serializable error shape that can cross the server/client component boundary (ApiError instances cannot). */
export interface ErrorInfo {
  status: number;
  errorCode: string;
  message: string;
  requestId?: string;
  traceId?: string;
  details?: unknown;
}

export function toErrorInfo(error: ApiError): ErrorInfo {
  return { status: error.status, errorCode: error.errorCode, message: error.message, requestId: error.requestId, traceId: error.traceId, details: error.details ?? null };
}

export function explainError(error: Pick<ErrorInfo, "errorCode" | "message">): ErrorExplanation {
  return EXPLANATIONS[error.errorCode] ?? { title: "Request failed", description: error.message, action: "Retry, and quote the request id if the problem persists." };
}
