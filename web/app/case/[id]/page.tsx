import type { Metadata } from "next";
import { Suspense, use } from "react";
import { CaseView } from "@/components/case/CaseView";

export const metadata: Metadata = { title: "Your case" };

function FromParams({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return <CaseView caseId={decodeURIComponent(id)} />;
}

// Params are read under Suspense so the shell prerenders (Cache Components).
export default function CasePage({ params }: PageProps<"/case/[id]">) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-ground" />}>
      <FromParams params={params} />
    </Suspense>
  );
}
