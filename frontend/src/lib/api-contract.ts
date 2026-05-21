export type ArtifactType = "image" | "pdf";
export type ArtifactStatus = "processing" | "ready" | "failed" | "archived";
export type ArtifactSort = "newest" | "oldest" | "title_az" | "title_za" | "most_comments" | "least_comments" | "recently_updated" | "recently_processed" | "status" | "type";

export type Artifact = {
  id: string;
  title: string;
  description: string;
  type: ArtifactType;
  tags: string[];
  category: string;
  ownerName: string;
  createdAt: string;
  updatedAt: string;
  processedAt?: string | null;
  status: ArtifactStatus;
  commentCount: number;
  artifactUrl: string;
  thumbnailUrl?: string | null;
  documentSummary?: string | null;
  feedbackSummary?: string | null;
  pageSummaries?: PageSummary[];
  processingError?: string | null;
  rating?: number | null;
};

export type PageSummary = {
  pageNumber: number;
  summary: string;
  imageUrl?: string | null;
};

export type Comment = {
  id: string;
  artifactId: string;
  authorName: string;
  body: string;
  createdAt: string;
  kind?: "question" | "decision" | "blocker" | "praise" | null;
};

export type Metrics = {
  totalDocuments: number;
  totalComments: number;
};

export type ArtifactListParams = {
  q?: string;
  type?: ArtifactType | "all";
  status?: ArtifactStatus | "all";
  sort?: ArtifactSort;
};

export type CreateArtifactsInput = {
  title: string;
  description: string;
  tags: string[];
  category: string;
  ownerName: string;
  files: File[];
};

export type CreateCommentInput = {
  body: string;
  kind?: Comment["kind"];
};

export type CreateShareLinkInput = {
  expiresInHours: 24 | 36 | 72;
  access: "anyone_with_link";
};

export type ShareLink = {
  url: string;
  expiresAt: string;
  expiresInHours: number;
};

export type DocumentSummaryResponse = {
  documentSummary: string;
  pageSummaries: PageSummary[];
};

export type FeedbackSummaryResponse = {
  feedbackSummary?: string | null;
};

export type McpConfig = {
  serverName: string;
  remoteMcpUrl: string;
  capabilities: string[];
  claude: { directUrl: string; messagesApiExample: unknown };
  codex: { directUrl: string; configTomlExample: string };
  note: string;
};
