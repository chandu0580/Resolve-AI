/**
 * Comparison key for search boxes and URL filters: Unicode NFKC (full-width letters fold to ASCII), invisible format characters
 * removed, lower-cased, whitespace collapsed. It is only used to compare; displayed text is never changed.
 */
export function foldForMatch(value: string | null | undefined): string {
  return (value ?? "")
    .normalize("NFKC")
    .replace(/\p{Cf}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}
