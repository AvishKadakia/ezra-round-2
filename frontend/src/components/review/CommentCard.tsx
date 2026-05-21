import type { Comment } from "@/lib/api-contract";
export function CommentCard({ comment }: { comment: Comment }) {
  return (
    <div className="flex min-w-0 gap-4 rounded-2xl border bg-slate-50 p-5">
      <div className="h-9 w-9 shrink-0 rounded-full bg-slate-200" />
      <div className="min-w-0">
        <p className="truncate-safe font-semibold text-slate-950" title={comment.authorName}>{comment.authorName}</p>
        <p className="mt-1 line-clamp-2-safe text-base text-slate-600" title={comment.body}>{comment.body}</p>
      </div>
    </div>
  );
}
