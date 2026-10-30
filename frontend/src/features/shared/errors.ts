import { ApiError } from '@/platform/api/client'

/** The message to show a person for any failure. Server messages are already written for people. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Something went wrong. Please try again.'
}
