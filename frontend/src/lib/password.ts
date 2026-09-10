/**
 * Client-side mirror of the backend password policy (spec GU-01: NIST SP
 * 800-63B — length is what matters, no special-character theatre).
 *
 * This is a UX aid only. The backend re-checks and is the authority; if the two
 * ever disagree the server wins and the form shows its `problems` list.
 */

export const MIN_PASSWORD_LENGTH = 12;

export function passwordProblems(password: string): string[] {
  const problems: string[] = [];
  if (password.length < MIN_PASSWORD_LENGTH) {
    problems.push(`must be at least ${MIN_PASSWORD_LENGTH} characters`);
  }
  if (!/\d/.test(password)) {
    problems.push("must contain at least one digit");
  }
  if (!/[a-zA-Z]/.test(password)) {
    problems.push("must contain at least one letter");
  }
  return problems;
}

export function isPasswordAcceptable(password: string): boolean {
  return passwordProblems(password).length === 0;
}
