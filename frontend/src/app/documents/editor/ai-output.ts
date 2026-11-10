/** Converts AI-generated Markdown-ish output into TipTap JSON and safe HTML.
 *
 * Providers are instructed to reply with simple Markdown: `#`-`######` headings,
 * `-`/`*`/`+` bullets, `1.` numbered lists, `>` quotes, `---` rules and inline
 * `**bold**`, `*italic*`, `` `code` ``, `~~strike~~` and `[text](url)` links.
 * This module parses that subset so accepted AI output lands in the document as
 * real headings and lists instead of flat paragraphs. It is intentionally
 * self-contained (no DOM or editor dependencies) so it is trivially testable.
 */

export interface AiMark {
  type: string;
  attrs?: Record<string, unknown>;
}

export interface AiInlineNode {
  type: 'text';
  text: string;
  marks?: AiMark[];
}

export interface AiBlockNode {
  type: string;
  attrs?: Record<string, unknown>;
  content?: (AiBlockNode | AiInlineNode)[];
}

interface ListItem {
  text: string;
  ordered: boolean;
  children: ListItem[];
}

interface RawListLine {
  indent: number;
  ordered: boolean;
  text: string;
}

const HEADING_RE = /^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/;
const RULE_RE = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const QUOTE_RE = /^\s*>\s?(.*)$/;
const LIST_RE = /^(\s*)([-*+]|\d{1,3}[.)])\s+(.+)$/;
const INLINE_RE =
  /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*\*([^*]+)\*\*|__([^_]+)__|\*([^*\n]+)\*|_([^_\n]+)_|`([^`]+)`|~~([^~]+)~~/g;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Parses inline Markdown marks into TipTap text nodes. */
export function parseInline(text: string): AiInlineNode[] {
  const nodes: AiInlineNode[] = [];
  let last = 0;
  INLINE_RE.lastIndex = 0;
  for (let match = INLINE_RE.exec(text); match; match = INLINE_RE.exec(text)) {
    if (match.index > last) {
      nodes.push({ type: 'text', text: text.slice(last, match.index) });
    }
    const [full, linkText, href, boldU, boldW, italS, italU, code, strike] = match;
    if (linkText !== undefined) {
      nodes.push({
        type: 'text',
        text: linkText,
        marks: [{ type: 'link', attrs: { href, target: '_blank' } }],
      });
    } else {
      const body = boldU ?? boldW ?? italS ?? italU ?? code ?? strike ?? '';
      const mark =
        boldU !== undefined || boldW !== undefined
          ? 'bold'
          : italS !== undefined || italU !== undefined
            ? 'italic'
            : code !== undefined
              ? 'code'
              : 'strike';
      nodes.push({ type: 'text', text: body, marks: [{ type: mark }] });
    }
    last = match.index + full.length;
  }
  if (last < text.length) {
    nodes.push({ type: 'text', text: text.slice(last) });
  }
  return nodes.filter((n) => n.text.length > 0);
}

function inlineToHtml(text: string): string {
  return parseInline(text)
    .map((node) => {
      let html = escapeHtml(node.text);
      for (const mark of node.marks ?? []) {
        const tag =
          mark.type === 'bold'
            ? 'strong'
            : mark.type === 'italic'
              ? 'em'
              : mark.type === 'code'
                ? 'code'
                : mark.type === 'strike'
                  ? 's'
                  : null;
        if (mark.type === 'link') {
          const href = escapeHtml(String(mark.attrs?.['href'] ?? ''));
          html = `<a href="${href}" target="_blank" rel="noopener">${html}</a>`;
        } else if (tag) {
          html = `<${tag}>${html}</${tag}>`;
        }
      }
      return html;
    })
    .join('');
}

function collectList(lines: string[], start: number): { items: RawListLine[]; end: number } {
  const items: RawListLine[] = [];
  let i = start;
  while (i < lines.length) {
    const match = LIST_RE.exec(lines[i]);
    if (!match) break;
    items.push({ indent: match[1].replace(/\t/g, '  ').length, ordered: /\d/.test(match[2]), text: match[3].trim() });
    i += 1;
  }
  return { items, end: i };
}

/** Groups flat list lines into a nesting tree based on relative indentation. */
function nestListItems(items: RawListLine[]): ListItem[] {
  const depths = [...new Set(items.map((i) => i.indent))].sort((a, b) => a - b);
  const roots: ListItem[] = [];
  const path: ListItem[] = [];
  for (const raw of items) {
    const depth = Math.max(0, depths.indexOf(raw.indent));
    const item: ListItem = { text: raw.text, ordered: raw.ordered, children: [] };
    path[depth] = item;
    path.length = depth + 1;
    if (depth === 0 || !path[depth - 1]) {
      roots.push(item);
    } else {
      path[depth - 1].children.push(item);
    }
  }
  return roots;
}

/** Emits TipTap list nodes; consecutive items with the same marker share a list. */
function listItemsToNodes(items: ListItem[]): AiBlockNode[] {
  const nodes: AiBlockNode[] = [];
  let current: AiBlockNode | null = null;
  for (const item of items) {
    const listType = item.ordered ? 'orderedList' : 'bulletList';
    if (!current || current.type !== listType) {
      current = { type: listType, content: [] };
      nodes.push(current);
    }
    const listItem: AiBlockNode = {
      type: 'listItem',
      content: [{ type: 'paragraph', content: parseInline(item.text) }],
    };
    (listItem.content as AiBlockNode[]).push(...listItemsToNodes(item.children));
    (current.content as AiBlockNode[]).push(listItem);
  }
  return nodes;
}

function listItemsToHtml(items: ListItem[]): string {
  let html = '';
  let openList: string | null = null;
  for (const item of items) {
    const tag = item.ordered ? 'ol' : 'ul';
    if (openList !== tag) {
      if (openList) html += `</${openList}>`;
      html += `<${tag}>`;
      openList = tag;
    }
    html += `<li>${inlineToHtml(item.text)}${listItemsToHtml(item.children)}</li>`;
  }
  if (openList) html += `</${openList}>`;
  return html;
}

function* blocks(output: string): Generator<
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'paragraph'; text: string }
  | { kind: 'quote'; text: string }
  | { kind: 'rule' }
  | { kind: 'list'; items: ListItem[] }
> {
  const lines = output.split(/\r?\n/);
  let para: string[] = [];
  const flush = function* (): Generator<{ kind: 'paragraph'; text: string }> {
    if (para.length) {
      yield { kind: 'paragraph', text: para.join(' ') };
      para = [];
    }
  };
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      yield* flush();
      i += 1;
      continue;
    }
    const heading = HEADING_RE.exec(line);
    if (heading) {
      yield* flush();
      yield { kind: 'heading', level: Math.min(6, heading[1].length), text: heading[2].trim() };
      i += 1;
      continue;
    }
    if (RULE_RE.test(line)) {
      yield* flush();
      yield { kind: 'rule' };
      i += 1;
      continue;
    }
    const quote = QUOTE_RE.exec(line);
    if (quote && !LIST_RE.test(line)) {
      yield* flush();
      yield { kind: 'quote', text: quote[1].trim() };
      i += 1;
      continue;
    }
    if (LIST_RE.test(line)) {
      yield* flush();
      const { items, end } = collectList(lines, i);
      yield { kind: 'list', items: nestListItems(items) };
      i = end;
      continue;
    }
    para.push(line.trim());
    i += 1;
  }
  yield* flush();
}

/** Parses AI Markdown-ish output into an array of TipTap block nodes. */
export function aiOutputToNodes(output: string): AiBlockNode[] {
  const nodes: AiBlockNode[] = [];
  for (const block of blocks(output)) {
    switch (block.kind) {
      case 'heading':
        nodes.push({ type: 'heading', attrs: { level: block.level }, content: parseInline(block.text) });
        break;
      case 'paragraph':
        nodes.push({ type: 'paragraph', content: parseInline(block.text) });
        break;
      case 'quote':
        nodes.push({
          type: 'blockquote',
          content: [{ type: 'paragraph', content: parseInline(block.text) }],
        });
        break;
      case 'rule':
        nodes.push({ type: 'horizontalRule' });
        break;
      case 'list':
        nodes.push(...listItemsToNodes(block.items));
        break;
    }
  }
  return nodes;
}

/** Serializes TipTap JSON content to Markdown so structure survives the round
 * trip through the provider. Used when sending the selection as AI context —
 * plain `textBetween` would discard headings and lists entirely. */
export function docToMarkdown(content: unknown[]): string {
  return (content as JsonNode[])
    .map((node) => blockToMarkdown(node, ''))
    .filter(Boolean)
    .join('\n\n')
    .trim();
}

interface JsonNode {
  type?: string;
  attrs?: Record<string, unknown>;
  content?: JsonNode[];
  text?: string;
  marks?: { type: string; attrs?: Record<string, unknown> }[];
}

function inlineToMarkdown(content: JsonNode[] | undefined): string {
  return (content ?? [])
    .map((node) => {
      let text = node.text ?? '';
      if (!text) return '';
      for (const mark of node.marks ?? []) {
        const wrap =
          mark.type === 'bold'
            ? '**'
            : mark.type === 'italic'
              ? '*'
              : mark.type === 'code'
                ? '`'
                : mark.type === 'strike'
                  ? '~~'
                  : null;
        if (wrap) text = wrap + text + wrap;
        if (mark.type === 'link' && mark.attrs?.['href']) {
          text = `[${text}](${String(mark.attrs['href'])})`;
        }
      }
      return text;
    })
    .join('');
}

function listItemToMarkdown(node: JsonNode, marker: string, indent: string): string {
  const blocks = node.content ?? [];
  const first = blocks[0];
  const text = first ? inlineToMarkdown(first.content) : '';
  const nested = blocks
    .slice(1)
    .map((child) => blockToMarkdown(child, indent + '  '))
    .filter(Boolean)
    .join('\n');
  return `${indent}${marker}${text}${nested ? '\n' + nested : ''}`;
}

function blockToMarkdown(node: JsonNode, indent: string): string {
  switch (node.type) {
    case 'heading':
      return `${indent}${'#'.repeat(Number(node.attrs?.['level'] ?? 1))} ${inlineToMarkdown(node.content)}`;
    case 'paragraph':
      return indent + inlineToMarkdown(node.content);
    case 'blockquote':
      return (node.content ?? [])
        .map((child) => '> ' + blockToMarkdown(child, ''))
        .join('\n');
    case 'horizontalRule':
      return '---';
    case 'bulletList':
      return (node.content ?? []).map((li) => listItemToMarkdown(li, '- ', indent)).join('\n');
    case 'orderedList':
      return (node.content ?? []).map((li, i) => listItemToMarkdown(li, `${i + 1}. `, indent)).join('\n');
    case 'codeBlock':
      return '```\n' + (node.content ?? []).map((n) => n.text ?? '').join('\n') + '\n```';
    default:
      // Bare inline text nodes appear when a selection slice starts/ends mid-paragraph.
      return indent + (node.text !== undefined ? inlineToMarkdown([node]) : inlineToMarkdown(node.content));
  }
}

/** Renders AI Markdown-ish output as safe, escaped HTML for the preview panel. */
export function aiOutputToHtml(output: string): string {
  const parts: string[] = [];
  for (const block of blocks(output)) {
    switch (block.kind) {
      case 'heading':
        parts.push(`<h${Math.min(4, block.level)}>${inlineToHtml(block.text)}</h${Math.min(4, block.level)}>`);
        break;
      case 'paragraph':
        parts.push(`<p>${inlineToHtml(block.text)}</p>`);
        break;
      case 'quote':
        parts.push(`<blockquote><p>${inlineToHtml(block.text)}</p></blockquote>`);
        break;
      case 'rule':
        parts.push('<hr>');
        break;
      case 'list':
        parts.push(listItemsToHtml(block.items));
        break;
    }
  }
  return parts.join('');
}
