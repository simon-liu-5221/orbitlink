import { Link } from "react-router-dom";

const TABS = [
  { key: "users", label: "Users", to: "/admin/users" },
  { key: "feedback", label: "Feedback", to: "/admin/feedback" },
] as const;

export function AdminNav({ active }: { active: "users" | "feedback" }) {
  return (
    <div className="flex items-center gap-2 border-b border-slate-200 pb-2">
      <h1 className="mr-4 text-lg font-semibold text-slate-900">Admin</h1>
      {TABS.map((tab) => (
        <Link
          key={tab.key}
          to={tab.to}
          className={`rounded-md px-3 py-1.5 text-sm ${
            active === tab.key
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {tab.label}
        </Link>
      ))}
    </div>
  );
}
