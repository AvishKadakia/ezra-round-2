import { Card, CardContent } from "@/components/ui/card";
export function PlaceholderPage({ title }: { title: string }) {
  return <Card><CardContent className="p-10"><h1 className="text-4xl font-bold text-slate-950">{title}</h1><p className="mt-3 max-w-2xl text-slate-500">This area is ready for the next product iteration.</p></CardContent></Card>;
}
