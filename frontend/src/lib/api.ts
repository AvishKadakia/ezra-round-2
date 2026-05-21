import type {
  Artifact,
  ArtifactListParams,
  Comment,
  CreateArtifactsInput,
  CreateCommentInput,
  CreateShareLinkInput,
  DocumentSummaryResponse,
  FeedbackSummaryResponse,
  McpConfig,
  Metrics,
  ShareLink,
} from "@/lib/api-contract";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
    this.name = "ApiError";
  }
}

async function readError(response: Response) {
  const text = await response.text().catch(() => "");
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    return parsed.detail ?? text;
  } catch {
    return text || `Request failed: ${response.status}`;
  }
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return response.json() as Promise<T>;
}

async function requestFormData<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "POST", body: formData });
  if (!response.ok) throw new ApiError(await readError(response), response.status);
  return response.json() as Promise<T>;
}

function buildQuery(params: ArtifactListParams) {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.type && params.type !== "all") search.set("type", params.type);
  if (params.status && params.status !== "all") search.set("status", params.status);
  if (params.sort) search.set("sort", params.sort);
  const queryString = search.toString();
  return queryString ? `?${queryString}` : "";
}

function resolveApiUrl(url?: string | null) {
  if (!url) return url;
  if (url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
  if (url.startsWith("/")) return `${API_BASE_URL}${url}`;
  return url;
}

function normalizeArtifact(artifact: Artifact): Artifact {
  return {
    ...artifact,
    artifactUrl: resolveApiUrl(artifact.artifactUrl) ?? artifact.artifactUrl,
    thumbnailUrl: resolveApiUrl(artifact.thumbnailUrl),
    pageSummaries: artifact.pageSummaries?.map((page) => ({
      ...page,
      imageUrl: resolveApiUrl(page.imageUrl),
    })),
  };
}

function normalizeArtifacts(artifacts: Artifact[]) {
  return artifacts.map(normalizeArtifact);
}

function createArtifactsFormData(input: CreateArtifactsInput) {
  const formData = new FormData();
  formData.append("title", input.title);
  formData.append("description", input.description);
  formData.append("category", input.category);
  formData.append("owner_name", input.ownerName);
  formData.append("tags", JSON.stringify(input.tags));
  input.files.forEach((file) => formData.append("files", file, file.name));
  return formData;
}

export const artifactApi = {
  async listArtifacts(params: ArtifactListParams = {}): Promise<Artifact[]> {
    return normalizeArtifacts(await requestJson<Artifact[]>(`/artifacts${buildQuery(params)}`));
  },
  getMetrics(): Promise<Metrics> {
    return requestJson<Metrics>("/metrics");
  },
  getMcpConfig(): Promise<McpConfig> {
    return requestJson<McpConfig>("/mcp-config");
  },
  async getArtifact(id: string): Promise<Artifact> {
    return normalizeArtifact(await requestJson<Artifact>(`/artifacts/${id}`));
  },
  async createArtifacts(input: CreateArtifactsInput): Promise<Artifact[]> {
    return normalizeArtifacts(await requestFormData<Artifact[]>("/artifacts/bulk", createArtifactsFormData(input)));
  },
  async getSharedArtifact(artifactId: string, token?: string): Promise<Artifact> {
    const queryString = token ? `?token=${encodeURIComponent(token)}` : "";
    return normalizeArtifact(await requestJson<Artifact>(`/share/${artifactId}${queryString}`));
  },
  listComments(artifactId: string): Promise<Comment[]> {
    return requestJson<Comment[]>(`/artifacts/${artifactId}/comments`);
  },
  createComment(artifactId: string, input: CreateCommentInput): Promise<Comment> {
    return requestJson<Comment>(`/artifacts/${artifactId}/comments`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },
  async refreshFeedbackSummary(artifactId: string): Promise<FeedbackSummaryResponse> {
    return requestJson<FeedbackSummaryResponse>(`/artifacts/${artifactId}/feedback-summary`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  },
  async refreshDocumentSummary(artifactId: string): Promise<DocumentSummaryResponse> {
    const response = await requestJson<DocumentSummaryResponse>(`/artifacts/${artifactId}/summaries`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    return {
      ...response,
      pageSummaries: response.pageSummaries.map((page) => ({
        ...page,
        imageUrl: resolveApiUrl(page.imageUrl),
      })),
    };
  },
  createShareLink(artifactId: string, input: CreateShareLinkInput): Promise<ShareLink> {
    return requestJson<ShareLink>(`/artifacts/${artifactId}/share-links`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },
};
