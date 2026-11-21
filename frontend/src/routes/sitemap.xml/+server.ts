import type { RequestHandler } from './$types';

/** Only the public landing page is listed; the app itself needs a login. */
export const GET: RequestHandler = ({ url }) =>
  new Response(
    `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n  <url><loc>${new URL('/', url.origin).href}</loc></url>\n</urlset>\n`,
    { headers: { 'content-type': 'application/xml' } }
  );
