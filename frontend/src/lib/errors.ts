// Narrow an unknown error to a user-facing string. Use in catch blocks
// instead of `catch (err: any)`.
export function errorMessage(err: unknown, fallback = "Something went wrong"): string {
  return err instanceof Error ? err.message : fallback;
}
