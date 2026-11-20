import { LinkButton } from "@/components/ui/Button";
import { useDocumentTitle } from "@/hooks/useUtilities";

export default function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-surface px-4 text-center">
      <p className="text-sm font-semibold text-brand-500">404</p>
      <h1 className="mt-2 text-2xl font-bold text-ink">We couldn't find that page</h1>
      <p className="mt-2 max-w-sm text-sm text-muted">The link may be broken or the page may have moved.</p>
      <LinkButton to="/" className="mt-6">
        Back to home
      </LinkButton>
    </div>
  );
}
