import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
  NEWS_API_URL: { schema: value => value?.trim() || undefined },
  CHAT_API_URL: { schema: value => value?.trim() || 'http://127.0.0.1:8000' },
  /** Signs the login cookie; set it in production so sessions survive restarts. */
  SESSION_SECRET: { schema: value => value?.trim() || undefined }
});
