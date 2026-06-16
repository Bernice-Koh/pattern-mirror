/**
 * The signed-in user shown in the app chrome. There is no auth yet, so this is
 * a placeholder; when a session exists, source it from the auth endpoint (e.g. a
 * `useCurrentUser` hook backed by TanStack Query) rather than a constant.
 * TODO(auth): replace with the real signed-in user.
 */
export const currentUser = {
  initials: 'DK',
} as const
