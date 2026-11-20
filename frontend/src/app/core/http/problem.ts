import { HttpErrorResponse } from '@angular/common/http';

/** RFC 7807 body returned by every API error. */
export interface Problem {
  type: string;
  title: string;
  status: number;
  detail: string;
  code: string;
  errors?: Record<string, string[] | string>;
}

export function asProblem(error: unknown): Problem | null {
  if (error instanceof HttpErrorResponse && error.error && typeof error.error === 'object') {
    const body = error.error as Partial<Problem>;
    if (typeof body.code === 'string') return body as Problem;
  }
  return null;
}

/** Human-readable French message for any thrown value. */
export function problemMessage(error: unknown, fallback = 'Une erreur est survenue.'): string {
  const problem = asProblem(error);
  if (problem) {
    const first = problem.errors ? Object.values(problem.errors)[0] : undefined;
    const fieldMessage = Array.isArray(first) ? first[0] : first;
    return problem.code === 'validation_error' && fieldMessage ? fieldMessage : problem.detail;
  }
  if (error instanceof HttpErrorResponse && error.status === 0) {
    return 'Connexion impossible : vérifiez votre réseau.';
  }
  return fallback;
}

export function problemCode(error: unknown): string | null {
  return asProblem(error)?.code ?? null;
}
