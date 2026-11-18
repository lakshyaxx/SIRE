import type { Capabilities } from "@/types/api";

/** Match published extensions as well as exact/wildcard browser MIME declarations. */
export function acceptsFile(
  file: Pick<File, "name" | "type">,
  accepted: string[],
): boolean {
  return accepted.some((rule) =>
    rule.startsWith(".")
      ? file.name.toLowerCase().endsWith(rule.toLowerCase())
      : rule.endsWith("/*")
        ? file.type.startsWith(rule.slice(0, -1))
        : file.type === rule,
  );
}

export function validateInvestigation(
  question: string,
  files: File[],
  uploadCapability?: Capabilities["uploads"],
) {
  const trimmed = question.trim();
  const questionError = !trimmed
    ? "Enter an investigation question."
    : trimmed.length < 10
      ? "Use at least 10 characters to make the question reviewable."
      : undefined;
  const fileErrors: string[] = [];
  if (files.length > 6)
    fileErrors.push("Use at most six attachments per investigation.");
  if (
    files.filter(
      (file) =>
        file.type.startsWith("image/") ||
        /\.(jpe?g|png|webp)$/i.test(file.name),
    ).length > 3
  )
    fileErrors.push("Use at most three images per investigation.");
  if (files.length && uploadCapability?.state !== "available") {
    fileErrors.push("Remove files because evidence upload is unavailable.");
  }
  for (const file of files) {
    if (uploadCapability?.maxBytes && file.size > uploadCapability.maxBytes) {
      fileErrors.push(`${file.name} exceeds the published size limit.`);
    }
    if (
      uploadCapability?.acceptedTypes?.length &&
      !acceptsFile(file, uploadCapability.acceptedTypes)
    ) {
      fileErrors.push(
        `${file.name} has an unsupported file type (${file.type || "unknown"}).`,
      );
    }
  }
  return {
    valid: !questionError && fileErrors.length === 0,
    questionError,
    fileErrors,
  };
}
