// See https://svelte.dev/docs/kit/types#app.d.ts
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			/** The signed-in business, set by `hooks.server.ts`; null when signed out. */
			account: import('#lib/server/accounts.ts').PublicAccount | null;
		}
		// interface PageData {}
		// interface PageState {}
		// interface Platform {}
	}
}

export {};
