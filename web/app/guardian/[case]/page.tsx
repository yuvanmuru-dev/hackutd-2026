import type { Metadata } from "next";
import { Suspense, use } from "react";
import { GuardianScreen } from "@/components/guardian/GuardianScreen";

export const metadata: Metadata = { title: "Guardian" };

function CaseFromParams({ params }: { params: Promise<{ case: string }> }) {
  const { case: caseId } = use(params);
  return <GuardianScreen caseId={decodeURIComponent(caseId)} />;
}

// Not async: params are read under Suspense so the shell prerenders (Cache Components).
export default function GuardianCasePage({ params }: PageProps<"/guardian/[case]">) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-black" />}>
      <CaseFromParams params={params} />
    </Suspense>
  );
}
