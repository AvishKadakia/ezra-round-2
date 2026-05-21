import { useState } from "react";
import type { Artifact } from "@/lib/api-contract";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useComments, useCreateComment, useRefreshFeedbackSummary } from "@/hooks/use-artifacts";
import { CommentCard } from "@/components/review/CommentCard";

export function ReviewPanel({ artifact }: { artifact: Artifact }) {
  const [draftComment, setDraftComment] = useState("");
  const commentsQuery = useComments(artifact.id);
  const createComment = useCreateComment(artifact.id);
  const refreshFeedback = useRefreshFeedbackSummary(artifact.id);

  async function handleSubmitComment() {
    const body = draftComment.trim();
    if (!body) return;
    await createComment.mutateAsync({ body });
    setDraftComment("");
  }

  return (
    <aside className="min-w-0 rounded-2xl border bg-white p-8 shadow-soft">
      <h2 className="line-clamp-2-safe text-4xl font-bold tracking-tight text-slate-950">Review workspace</h2>
      <p className="mt-2 line-clamp-2-safe text-base text-slate-500">Comments and decisions in one focused panel.</p>
      {(artifact.feedbackSummary || artifact.commentCount > 0) && (
        <section className="mt-6 rounded-2xl border border-emerald-100 bg-emerald-50 p-5">
          <div className="flex items-center justify-between gap-3">
            <h3 className="truncate-safe text-lg font-semibold text-slate-950">Feedback summary</h3>
            <Button type="button" size="sm" variant="outline" disabled={refreshFeedback.isPending} onClick={() => refreshFeedback.mutate()}>
              {refreshFeedback.isPending ? "Refreshing..." : "Refresh"}
            </Button>
          </div>
          <p className="mt-3 text-sm leading-6 text-emerald-900">
            {artifact.feedbackSummary || "Feedback exists. Refresh to generate a summary."}
          </p>
        </section>
      )}

      <div className="mt-8 space-y-4">
        {commentsQuery.data?.map((comment) => <CommentCard key={comment.id} comment={comment} />)}
      </div>
      <div className="mt-4 flex gap-3">
        <Textarea value={draftComment} placeholder="Add structured feedback..." rows={1} onChange={(event) => setDraftComment(event.target.value)} />
        <Button size="sm" disabled={createComment.isPending} onClick={handleSubmitComment}>Add</Button>
      </div>
    </aside>
  );
}
