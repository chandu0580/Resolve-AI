/**
 * Renders the evaluation's own markdown artifacts (misleading_headline.md, statistical_uncertainty.md) without HTML injection:
 * headings, paragraphs, ordered/unordered lists (keeping the document's own numbering), pipe tables, **bold** and `code`.
 */
import { Fragment, type ReactNode } from "react";

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "ol"; items: { value: number; text: string }[] }
  | { kind: "ul"; items: string[] }
  | { kind: "table"; header: string[]; rows: string[][] };

const cells = (line: string) =>
  line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((c) => c.trim());

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i++;
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      i++;
      continue;
    }
    if (line.trim().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) tableLines.push(lines[i++]);
      const body = tableLines.filter((l) => !/^\|?\s*:?-{2,}/.test(l.trim()));
      blocks.push({ kind: "table", header: cells(body[0] ?? ""), rows: body.slice(1).map(cells) });
      continue;
    }
    if (/^\d+\.\s/.test(line)) {
      const items: { value: number; text: string }[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i])) {
        const m = /^(\d+)\.\s+(.*)$/.exec(lines[i++])!;
        items.push({ value: Number(m[1]), text: m[2] });
      }
      blocks.push({ kind: "ol", items });
      continue;
    }
    if (/^[-*]\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s/.test(lines[i])) items.push(lines[i++].replace(/^[-*]\s+/, ""));
      blocks.push({ kind: "ul", items });
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|\||\d+\.\s|[-*]\s)/.test(lines[i])) para.push(lines[i++].trim());
    blocks.push({ kind: "paragraph", text: para.join(" ") });
  }
  return blocks;
}

function inline(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <strong key={i} className="font-semibold text-ink">{p.slice(2, -2)}</strong>;
    if (p.startsWith("`") && p.endsWith("`")) return <code key={i} className="rounded bg-subtle px-1 font-mono text-[12px] break-all">{p.slice(1, -1)}</code>;
    return <Fragment key={i}>{p}</Fragment>;
  });
}

export function Markdown({ source, skipFirstHeading = false }: { source: string; skipFirstHeading?: boolean }) {
  let blocks = parseMarkdown(source);
  if (skipFirstHeading && blocks[0]?.kind === "heading") blocks = blocks.slice(1);
  return (
    <div className="space-y-3 text-[13px] leading-relaxed text-ink-2">
      {blocks.map((b, i) => {
        switch (b.kind) {
          case "heading":
            return b.level <= 2 ? (
              <h3 key={i} className="text-sm font-semibold text-ink">{inline(b.text)}</h3>
            ) : (
              <h4 key={i} className="text-[13px] font-semibold text-ink">{inline(b.text)}</h4>
            );
          case "paragraph":
            return <p key={i}>{inline(b.text)}</p>;
          case "ol":
            return (
              <ol key={i} className="list-decimal space-y-2 pl-6">
                {b.items.map((it) => (
                  <li key={it.value} value={it.value} className="pl-1">
                    {inline(it.text)}
                  </li>
                ))}
              </ol>
            );
          case "ul":
            return (
              <ul key={i} className="list-disc space-y-1 pl-6">
                {b.items.map((it, j) => (
                  <li key={j}>{inline(it)}</li>
                ))}
              </ul>
            );
          case "table":
            return (
              <div key={i} className="overflow-x-auto rounded-md border border-line" tabIndex={0} role="region" aria-label={`Table: ${b.header.slice(0, 3).join(", ")}`}>
                <table className="w-full text-left text-xs">
                  <thead className="bg-subtle text-ink-2">
                    <tr>
                      {b.header.map((h, j) => (
                        <th key={j} scope="col" className="px-2.5 py-2 font-medium whitespace-nowrap">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="tabular">
                    {b.rows.map((r, j) => (
                      <tr key={j} className="border-t border-line">
                        {r.map((c, k) => (
                          <td key={k} className={`px-2.5 py-1.5 whitespace-nowrap ${k === 0 ? "font-mono text-ink" : ""}`}>
                            {inline(c)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
        }
      })}
    </div>
  );
}
