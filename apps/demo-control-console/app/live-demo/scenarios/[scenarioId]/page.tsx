import { notFound, redirect } from "next/navigation";

const SUPPORTED = new Set(["SCN-001", "SCN-002", "SCN-003", "SCN-004", "SCN-010"]);

export default async function ScenarioWorkspacePage(props: PageProps<"/live-demo/scenarios/[scenarioId]">) {
  const { scenarioId } = await props.params;
  const normalized = scenarioId.toUpperCase();
  if (!SUPPORTED.has(normalized)) notFound();
  redirect(`/live-demo#${normalized}`);
}
