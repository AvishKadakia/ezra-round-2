import type { ArtifactListParams } from "@/lib/api-contract";

export const queryKeys = {
  artifacts: (params: ArtifactListParams) => ["artifacts", params] as const,
  artifact: (id: string) => ["artifact", id] as const,
  sharedArtifact: (id: string, token?: string) => ["shared-artifact", id, token] as const,
  comments: (artifactId: string) => ["comments", artifactId] as const,
  metrics: () => ["metrics"] as const,
  mcpConfig: () => ["mcp-config"] as const,
};
