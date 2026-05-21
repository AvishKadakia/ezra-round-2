import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { artifactApi } from "@/lib/api";
import type { ArtifactListParams, CreateArtifactsInput, CreateCommentInput, CreateShareLinkInput } from "@/lib/api-contract";
import { queryKeys } from "@/lib/query-keys";

export function useArtifacts(params: ArtifactListParams) {
  return useQuery({
    queryKey: queryKeys.artifacts(params),
    queryFn: () => artifactApi.listArtifacts(params),
    refetchInterval: (query) => query.state.data?.some((artifact) => artifact.status === "processing") ? 3000 : false,
  });
}

export function useMetrics() {
  return useQuery({ queryKey: queryKeys.metrics(), queryFn: () => artifactApi.getMetrics() });
}

export function useMcpConfig() {
  return useQuery({ queryKey: queryKeys.mcpConfig(), queryFn: () => artifactApi.getMcpConfig() });
}

export function useArtifact(id: string) {
  return useQuery({
    queryKey: queryKeys.artifact(id),
    queryFn: () => artifactApi.getArtifact(id),
    enabled: Boolean(id),
    refetchInterval: (query) => query.state.data?.status === "processing" ? 2500 : false,
  });
}

export function useCreateArtifacts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateArtifactsInput) => artifactApi.createArtifacts(input),
    onSuccess: (artifacts) => {
      queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics() });
      artifacts.forEach((artifact) => queryClient.setQueryData(queryKeys.artifact(artifact.id), artifact));
    },
  });
}

export function useSharedArtifact(artifactId: string, token?: string) {
  return useQuery({
    queryKey: queryKeys.sharedArtifact(artifactId, token),
    queryFn: () => artifactApi.getSharedArtifact(artifactId, token),
    enabled: Boolean(artifactId),
    refetchInterval: (query) => query.state.data?.status === "processing" ? 2500 : false,
  });
}

export function useComments(artifactId: string) {
  return useQuery({
    queryKey: queryKeys.comments(artifactId),
    queryFn: () => artifactApi.listComments(artifactId),
    enabled: Boolean(artifactId),
  });
}

export function useCreateComment(artifactId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateCommentInput) => artifactApi.createComment(artifactId, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.comments(artifactId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.artifact(artifactId) });
      queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      queryClient.invalidateQueries({ queryKey: queryKeys.metrics() });
    },
  });
}

export function useRefreshFeedbackSummary(artifactId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => artifactApi.refreshFeedbackSummary(artifactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.artifact(artifactId) });
      queryClient.invalidateQueries({ queryKey: ["artifacts"] });
    },
  });
}

export function useRefreshDocumentSummary(artifactId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => artifactApi.refreshDocumentSummary(artifactId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.artifact(artifactId) }),
  });
}

export function useCreateShareLink(artifactId: string) {
  return useMutation({ mutationFn: (input: CreateShareLinkInput) => artifactApi.createShareLink(artifactId, input) });
}
