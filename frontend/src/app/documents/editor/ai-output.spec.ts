import { describe, expect, it } from 'vitest';

import { aiOutputToHtml, aiOutputToNodes, docToMarkdown, parseInline } from './ai-output';

describe('aiOutputToNodes', () => {
  it('returns a single paragraph for plain text', () => {
    expect(aiOutputToNodes('Hello world.')).toEqual([
      { type: 'paragraph', content: [{ type: 'text', text: 'Hello world.' }] },
    ]);
  });

  it('maps markdown headings to heading nodes at the right level', () => {
    const nodes = aiOutputToNodes('# Title\n\n## Section\n\n### Sub');
    expect(nodes.map(n => [n.type, n.attrs?.['level']])).toEqual([
      ['heading', 1], ['heading', 2], ['heading', 3],
    ]);
  });

  it('maps dashes to a bullet list and numbers to an ordered list', () => {
    const nodes = aiOutputToNodes('- one\n- two\n\n1. first\n2. second');
    expect(nodes[0].type).toBe('bulletList');
    expect(nodes[1].type).toBe('orderedList');
    const items = nodes[0].content as { type: string }[];
    expect(items).toHaveLength(2);
    expect(items[0].type).toBe('listItem');
  });

  it('nests indented bullets inside the parent list item', () => {
    const nodes = aiOutputToNodes('- parent\n  - child\n- sibling');
    const list = nodes[0];
    const items = list.content as { type: string; content: { type: string }[] }[];
    expect(items).toHaveLength(2);
    const nested = items[0].content.find(n => n.type === 'bulletList');
    expect(nested).toBeTruthy();
    expect(items[1].content.every(n => n.type !== 'bulletList')).toBe(true);
  });

  it('merges consecutive plain lines into one paragraph', () => {
    const nodes = aiOutputToNodes('line one\nline two');
    expect(nodes).toHaveLength(1);
    expect(nodes[0].content).toEqual([{ type: 'text', text: 'line one line two' }]);
  });

  it('maps horizontal rules and blockquotes', () => {
    const nodes = aiOutputToNodes('above\n\n---\n\n> a wise note');
    expect(nodes.map(n => n.type)).toEqual(['paragraph', 'horizontalRule', 'blockquote']);
  });

  it('parses inline bold, italic, code, strike and links', () => {
    const nodes = parseInline('a **b** and *c* plus `d` ~~e~~ [f](https://x.dev)');
    const marks = nodes.flatMap(n => (n.marks ?? []).map(m => m.type));
    expect(marks).toEqual(['bold', 'italic', 'code', 'strike', 'link']);
    expect(nodes[0].text).toBe('a ');
    expect(nodes.at(-1)?.marks?.[0].attrs?.['href']).toBe('https://x.dev');
  });

  it('handles a realistic structured draft', () => {
    const draft = [
      '# Soil Health',
      '',
      'Agriculture depends on soil.',
      '',
      '## Methods',
      '',
      '- Rotate crops',
      '  - Legumes fix nitrogen',
      '- Reduce tillage',
      '',
      '## Steps',
      '',
      '1. Test the soil',
      '2. Amend as needed',
    ].join('\n');
    const nodes = aiOutputToNodes(draft);
    expect(nodes.map(n => n.type)).toEqual([
      'heading', 'paragraph', 'heading', 'bulletList', 'heading', 'orderedList',
    ]);
  });
});

describe('docToMarkdown', () => {
  it('serializes headings, lists and paragraphs to markdown', () => {
    const content = [
      { type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: 'Title' }] },
      { type: 'paragraph', content: [{ type: 'text', text: 'Body' }] },
      {
        type: 'bulletList',
        content: [
          { type: 'listItem', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'one' }] }] },
          { type: 'listItem', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'two' }] }] },
        ],
      },
    ];
    expect(docToMarkdown(content)).toBe('## Title\n\nBody\n\n- one\n- two');
  });

  it('serializes inline marks and bare text nodes from mid-paragraph slices', () => {
    const content = [
      { type: 'text', text: 'bold', marks: [{ type: 'bold' }] },
      { type: 'text', text: ' plain' },
    ];
    expect(docToMarkdown(content)).toBe('**bold**\n\n plain');
  });

  it('numbers ordered list items', () => {
    const content = [
      {
        type: 'orderedList',
        content: [1, 2].map(() => ({
          type: 'listItem',
          content: [{ type: 'paragraph', content: [{ type: 'text', text: 'x' }] }],
        })),
      },
    ];
    expect(docToMarkdown(content)).toBe('1. x\n2. x');
  });
});

describe('aiOutputToHtml', () => {
  it('escapes raw HTML in model output', () => {
    const html = aiOutputToHtml('<img src=x onerror=alert(1)>');
    expect(html).toContain('&lt;img');
    expect(html).not.toContain('<img');
  });

  it('renders headings and lists as HTML', () => {
    const html = aiOutputToHtml('## Title\n\n- a\n- b');
    expect(html).toContain('<h2>Title</h2>');
    expect(html).toContain('<ul><li>a</li><li>b</li></ul>');
  });

  it('renders inline emphasis safely', () => {
    const html = aiOutputToHtml('say **yes**');
    expect(html).toBe('<p>say <strong>yes</strong></p>');
  });
});
