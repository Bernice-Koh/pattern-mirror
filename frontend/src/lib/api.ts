/** Base URL for backend calls. Empty in dev so requests stay relative and the
 *  Vite proxy forwards them; an env override exists only as an escape hatch. */

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''
