import { FormEvent, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, Upload, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useCreateArtifacts } from "@/hooks/use-artifacts";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const MAX_TITLE_PREFIX_CHARS = 80;
const ACCEPTED_ARTIFACT_FILE_TYPES = ["application/pdf", "image/png", "image/jpeg", "image/webp", "image/gif"].join(",");
const TAG_PATTERN = /^[a-zA-Z0-9][a-zA-Z0-9_-]{0,31}$/;
const ALLOWED_EXTENSIONS = new Set(["pdf", "png", "jpg", "jpeg", "webp", "gif"]);

type TagValidation = { tags: string[]; error: string | null; normalizedText: string };

type FileValidation = { validFiles: File[]; error: string | null };

function validateTags(value: string): TagValidation {
  const rawParts = value.split(",");
  const parts = rawParts.map((tag) => tag.trim()).filter(Boolean);
  const normalized = Array.from(new Set(parts.map((tag) => tag.toLowerCase())));

  if (value.includes(",,") || /,\s*,/.test(value)) {
    return { tags: [], error: "Remove empty tag slots between commas.", normalizedText: normalized.join(", ") };
  }
  if (normalized.length > 12) return { tags: [], error: "Use 12 tags or fewer.", normalizedText: normalized.join(", ") };
  for (const tag of normalized) {
    if (!TAG_PATTERN.test(tag)) {
      return { tags: [], error: `Invalid tag "${tag}". Use letters, numbers, hyphen, or underscore only.`, normalizedText: normalized.join(", ") };
    }
  }
  return { tags: normalized, error: null, normalizedText: normalized.join(", ") };
}

function validateSelectedFiles(fileList: File[]): FileValidation {
  for (const file of fileList) {
    const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
    const isAllowedExtension = ALLOWED_EXTENSIONS.has(extension);
    const isAllowedMime = file.type === "application/pdf" || file.type.startsWith("image/");

    if (!isAllowedExtension || !isAllowedMime) {
      return { validFiles: [], error: `${file.name} is not allowed. Upload PDFs or image files only.` };
    }
    if (file.size > MAX_FILE_BYTES) {
      return { validFiles: [], error: `${file.name} is ${(file.size / 1024 / 1024).toFixed(1)} MB. Maximum allowed size is 10 MB.` };
    }
  }
  return { validFiles: fileList, error: null };
}

export function PublishArtifactDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const createArtifacts = useCreateArtifacts();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [category, setCategory] = useState("general");
  const [ownerName, setOwnerName] = useState("You");
  const [files, setFiles] = useState<File[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [acceptedMessage, setAcceptedMessage] = useState<string | null>(null);
  const tagValidation = useMemo(() => validateTags(tagsText), [tagsText]);

  function resetForm() {
    setTitle("");
    setDescription("");
    setTagsText("");
    setCategory("general");
    setOwnerName("You");
    setFiles([]);
    setFormError(null);
    setAcceptedMessage(null);
  }

  function handleClose() {
    if (!createArtifacts.isPending) {
      resetForm();
      onClose();
    }
  }

  function handleFileSelection(nextFiles: File[]) {
    const result = validateSelectedFiles(nextFiles);
    setAcceptedMessage(null);
    setFormError(result.error);
    setFiles(result.validFiles);
  }

  function removeFile(name: string, size: number) {
    setFiles((current) => current.filter((file) => !(file.name === name && file.size === size)));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (title.trim().length > MAX_TITLE_PREFIX_CHARS) {
      setFormError(`Title prefix must be ${MAX_TITLE_PREFIX_CHARS} characters or fewer.`);
      return;
    }
    if (tagValidation.error) {
      setFormError(tagValidation.error);
      return;
    }
    const fileValidation = validateSelectedFiles(files);
    if (fileValidation.error) {
      setFormError(fileValidation.error);
      return;
    }
    if (files.length === 0) {
      setFormError("Choose at least one image or PDF file.");
      return;
    }

    try {
      const artifacts = await createArtifacts.mutateAsync({
        title: title.trim(),
        description: description.trim(),
        tags: tagValidation.tags,
        category: category.trim() || "general",
        ownerName: ownerName.trim() || "You",
        files,
      });

      setAcceptedMessage(`${artifacts.length} file${artifacts.length === 1 ? "" : "s"} uploaded to blob storage and queued for background processing.`);
      resetForm();
      onClose();
      // Stay on the gallery so users can watch processing cards appear/update.
      // React Query polling refreshes processing artifacts until the worker marks them ready.
      navigate("/");
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Upload failed. Check the storage/backend configuration and try again.");
    }
  }

  return (
    <Dialog open={open} title="Publish artifacts" onClose={handleClose} maxWidth="max-w-2xl">
      <form className="flex max-h-[calc(90vh-7rem)] min-h-0 flex-col" onSubmit={handleSubmit}>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          <div>
            <div className="mb-2 flex items-center justify-between gap-3">
              <label className="block text-sm font-medium text-slate-600">Title prefix</label>
              <span className={`text-xs ${title.length >= MAX_TITLE_PREFIX_CHARS ? "text-red-600" : "text-slate-400"}`}>
                {title.length}/{MAX_TITLE_PREFIX_CHARS}
              </span>
            </div>
            <Input
              value={title}
              maxLength={MAX_TITLE_PREFIX_CHARS}
              placeholder="Optional. Used directly for one file; as prefix for multiple files."
              onChange={(event) => setTitle(event.target.value.slice(0, MAX_TITLE_PREFIX_CHARS))}
            />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-600">Description</label>
            <Textarea value={description} placeholder="Short description for reviewers..." rows={3} onChange={(event) => setDescription(event.target.value)} />
          </div>
          <div className="grid gap-4 md:grid-cols-[1fr_0.8fr]">
            <div className="min-w-0">
              <label className="mb-2 block text-sm font-medium text-slate-600">Tags</label>
              <Input value={tagsText} placeholder="frontend, marketing, launch" onChange={(event) => setTagsText(event.target.value)} />
              {tagsText && !tagValidation.error && <p className="mt-1 truncate text-xs text-slate-500">Normalized: {tagValidation.normalizedText || "none"}</p>}
              {tagValidation.error && <p className="mt-1 text-xs text-red-600">{tagValidation.error}</p>}
            </div>
            <div className="min-w-0">
              <label className="mb-2 block text-sm font-medium text-slate-600">Category</label>
              <Input value={category} placeholder="marketing" onChange={(event) => setCategory(event.target.value)} />
            </div>
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-600">Created by</label>
            <Input value={ownerName} placeholder="Your name, team, or workflow" onChange={(event) => setOwnerName(event.target.value)} />
          </div>
          <div>
            <label className="mb-2 block text-sm font-medium text-slate-600">Bulk upload artifact files</label>
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed bg-slate-50 p-6 text-center transition-colors hover:bg-slate-100">
              <Upload className="mb-3 h-7 w-7 text-slate-500" />
              <span className="font-medium text-slate-950">{files.length ? "Change selected files" : "Choose one or more files"}</span>
              <span className="mt-1 text-sm text-slate-500">Images or PDFs only · 10 MB max per file</span>
              <Input type="file" multiple accept={ACCEPTED_ARTIFACT_FILE_TYPES} className="sr-only" onChange={(event) => handleFileSelection(Array.from(event.target.files ?? []))} />
            </label>
            {files.length > 0 && (
              <div className="mt-3 max-h-48 space-y-2 overflow-y-auto rounded-2xl border bg-slate-50 p-2">
                {files.map((file) => (
                  <div key={`${file.name}-${file.size}`} className="flex min-w-0 items-center gap-3 rounded-xl border bg-white p-3 text-sm text-slate-600">
                    <FileText className="h-5 w-5 shrink-0 text-slate-500" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-slate-950" title={file.name}>{file.name}</p>
                      <p className="truncate">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                    </div>
                    <Button type="button" variant="ghost" size="icon" aria-label={`Remove ${file.name}`} onClick={() => removeFile(file.name, file.size)}>
                      <X className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
          {(formError || createArtifacts.isError) && (
            <p className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {formError || (createArtifacts.error instanceof Error ? createArtifacts.error.message : "Upload failed. Check your backend endpoint and try again.")}
            </p>
          )}
          {acceptedMessage && (
            <p className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
              {acceptedMessage}
            </p>
          )}
        </div>

        <div className="sticky bottom-0 mt-4 flex justify-end gap-3 border-t bg-white pt-4">
          <Button type="button" variant="outline" onClick={handleClose} disabled={createArtifacts.isPending}>Cancel</Button>
          <Button type="submit" disabled={createArtifacts.isPending}>{createArtifacts.isPending ? "Uploading to storage..." : `Publish ${files.length || ""} artifact${files.length === 1 ? "" : "s"}`}</Button>
        </div>
      </form>
    </Dialog>
  );
}
