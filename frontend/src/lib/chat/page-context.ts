import { onMount } from 'svelte';

export type PageContext = { path: string; title: string; content: string };

let detailsProvider: (() => string) | null = null;

/**
 * Lets a page add data the owner can see but that is not plain text on screen
 * (e.g. the values behind a chart, or table rows that are collapsed). Call during component setup.
 */
export function providePageDetails(provider: () => string): void {
  onMount(() => {
    detailsProvider = provider;
    return () => { if (detailsProvider === provider) detailsProvider = null; };
  });
}

const tidy = (text: string) => text.replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim();

/** Captures what the current page shows, so the assistant can answer questions about it. */
export function collectPageContext(): PageContext | null {
  const workspace = document.getElementById('workspace');
  if (!workspace || location.pathname.startsWith('/assistant')) return null;
  const visible = tidy(workspace.innerText).slice(0, 6000);
  const details = tidy(detailsProvider?.() ?? '').slice(0, 2000);
  const content = details ? `${visible}\n\nData behind this page:\n${details}` : visible;
  return { path: location.pathname, title: document.title || 'Current', content };
}
