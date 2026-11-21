// Minimal Markdown subset for assistant replies, rendered as Svelte elements (no {@html}, so model output stays inert).
export type Inline = { text: string; strong: boolean }[];
export type Block =
  | { kind: 'heading'; text: Inline }
  | { kind: 'paragraph'; lines: Inline[] }
  | { kind: 'list'; ordered: boolean; items: Inline[] };

const inline = (text: string): Inline =>
  text.split(/\*\*(.+?)\*\*/g).map((part, index) => ({ text: part, strong: index % 2 === 1 })).filter(part => part.text);

export function parseMarkdown(source: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of source.replace(/\r/g, '').split('\n')) {
    const line = raw.trim();
    const previous = blocks.at(-1);
    const bullet = line.match(/^[-*•]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    const heading = line.match(/^#{1,6}\s+(.*)$/);
    if (!line) blocks.push({ kind: 'paragraph', lines: [] });
    else if (heading) blocks.push({ kind: 'heading', text: inline(heading[1]) });
    else if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const item = inline((bullet ?? numbered)![1]);
      if (previous?.kind === 'list' && previous.ordered === ordered) previous.items.push(item);
      else blocks.push({ kind: 'list', ordered, items: [item] });
    } else if (previous?.kind === 'paragraph') previous.lines.push(inline(line));
    else blocks.push({ kind: 'paragraph', lines: [inline(line)] });
  }
  return blocks.filter(block => block.kind !== 'paragraph' || block.lines.length);
}
