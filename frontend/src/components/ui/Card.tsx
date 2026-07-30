    import type { ReactNode } from "react";

    interface CardProps {
    title?: string;
    children: ReactNode;
    className?: string;
    }

    export default function Card({
    title,
    children,
    className = "",
    }: CardProps) {
    return (
        <section
        className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}
        >
        {title && (
            <div className="border-b border-slate-100 px-6 py-4">
            <h2 className="text-lg font-semibold text-slate-900">
                {title}
            </h2>
            </div>
        )}

        <div className="p-6">{children}</div>
        </section>
    );
    }