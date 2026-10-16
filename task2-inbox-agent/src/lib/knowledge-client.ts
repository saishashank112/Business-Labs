import { SourceRef } from "./schemas";

export interface KnowledgeResponse {
  success: boolean;
  answer: string;
  status: "answered" | "insufficient_evidence" | "unavailable" | "error";
  error_code?: "QUOTA_EXHAUSTED" | "RATE_LIMITED" | "LLM_UNAVAILABLE" | "TIMEOUT" | "INVALID_OUTPUT" | "INTERNAL_ERROR" | null;
  sources: SourceRef[];
  images: Array<{ url: string; description: string; article_url: string }>;
  needs_human: boolean;
  escalation_id?: string | null;
  request_id?: string;
  error?: string;
}

export class KnowledgeBrainClient {
  private baseUrl: string;
  private apiKey: string;
  private timeoutMs: number;

  constructor(
    baseUrl: string = process.env.T1_BASE_URL || "http://localhost:8001",
    apiKey: string = process.env.T1_API_KEY || "change-me-in-production",
    timeoutMs: number = 10000,
  ) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.apiKey = apiKey;
    this.timeoutMs = timeoutMs;
  }

  async query(
    question: string,
    context?: string,
    mode: "vector" | "keyword" | "hybrid" = "hybrid",
  ): Promise<KnowledgeResponse> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(`${this.baseUrl}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": this.apiKey,
        },
        body: JSON.stringify({ question, context, mode }),
        signal: controller.signal,
      });

      clearTimeout(timer);

      if (!response.ok) {
        const errorText = await response.text().catch(() => "");
        return {
          success: false,
          answer: "Knowledge service unavailable. (HTTP error)",
          status: "unavailable",
          error_code: response.status === 429 ? "RATE_LIMITED" : response.status === 503 ? "LLM_UNAVAILABLE" : "INTERNAL_ERROR",
          sources: [],
          images: [],
          needs_human: true,
          error: `HTTP ${response.status}: ${errorText}`,
        };
      }

      const data = await response.json();
      return {
        success: true,
        answer: data.answer || "",
        status: data.status || "answered",
        error_code: data.error_code || null,
        sources: (data.sources || []).map((s: any) => ({
          title: s.title || "",
          url: s.url || "",
          relevance: s.relevance,
        })),
        images: data.images || [],
        needs_human: !!data.needs_human,
        escalation_id: data.escalation_id,
        request_id: data.request_id,
      };
    } catch (err: any) {
      clearTimeout(timer);
      const isTimeout = err.name === "AbortError";
      return {
        success: false,
        answer: "Knowledge service unavailable.",
        status: "unavailable",
        error_code: isTimeout ? "TIMEOUT" : "LLM_UNAVAILABLE",
        sources: [],
        images: [],
        needs_human: true,
        error: isTimeout ? "Request timed out after 10s" : err.message || "Network error",
      };
    }
  }
}
