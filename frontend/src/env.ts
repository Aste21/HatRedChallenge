import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
  NEWS_API_URL: { schema: value => value?.trim() || undefined },
  CHAT_API_URL: { schema: value => value?.trim() || 'http://localhost:8000' }
});
