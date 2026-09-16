const STARS = [1, 2, 3, 4, 5] as const;

export function StarRating({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (rating: number) => void;
}) {
  return (
    <div role="radiogroup" aria-label="Rating" className="flex gap-1">
      {STARS.map((star) => {
        const active = value !== null && star <= value;
        return (
          <button
            key={star}
            type="button"
            role="radio"
            aria-checked={value === star}
            aria-label={`${star} star${star === 1 ? "" : "s"}`}
            onClick={() => onChange(star)}
            className={`text-2xl leading-none transition-colors ${
              active ? "text-amber-400" : "text-slate-300 hover:text-amber-300"
            }`}
          >
            ★
          </button>
        );
      })}
    </div>
  );
}
