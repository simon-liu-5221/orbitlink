import type { FormEvent } from "react";
import { useState } from "react";

import { Button, FormError, FormNotice } from "@/components/ui";

import { feedbackApi } from "./api";
import { StarRating } from "./StarRating";

const MAX_COMMENT_LENGTH = 2000;

export function FeedbackModal({ onClose }: { onClose: () => void }) {
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (rating === null) return;

    setSubmitting(true);
    setError(null);
    try {
      await feedbackApi.submit({ rating, comment: comment.trim() || null });
      setDone(true);
    } catch {
      setError("Couldn't send your feedback. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  function sendAnother() {
    setRating(null);
    setComment("");
    setDone(false);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label="Send feedback"
        className="w-full max-w-sm rounded-xl bg-white p-6 shadow-lg"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Feedback</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="text-slate-400 hover:text-slate-600"
          >
            ✕
          </button>
        </div>

        {done ? (
          <div className="space-y-4">
            <FormNotice>Thanks for letting us know!</FormNotice>
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={sendAnother}>
                Send more
              </Button>
              <Button onClick={onClose}>Done</Button>
            </div>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={onSubmit}>
            <FormError>{error}</FormError>
            <div>
              <p className="mb-1 text-sm font-medium text-slate-700">
                How's OrbitLink working for you?
              </p>
              <StarRating value={rating} onChange={setRating} />
            </div>
            <div>
              <label
                htmlFor="feedback-comment"
                className="mb-1 block text-sm font-medium text-slate-700"
              >
                Comments (optional)
              </label>
              <textarea
                id="feedback-comment"
                rows={3}
                maxLength={MAX_COMMENT_LENGTH}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm outline-none focus:border-slate-900 focus:ring-1 focus:ring-slate-900"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={rating === null}
                loading={submitting}
              >
                Send feedback
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
