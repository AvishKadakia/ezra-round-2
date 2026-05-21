import { Outlet } from "react-router-dom";
import { TopNav } from "@/components/layout/TopNav";

type AppShellProps = {
  searchValue: string;
  onSearchChange: (value: string) => void;
  onPublishClick: () => void;
};

export function AppShell({ searchValue, onSearchChange, onPublishClick }: AppShellProps) {
  return (
    <div className="app-background min-h-screen px-5 py-8">
      <TopNav searchValue={searchValue} onSearchChange={onSearchChange} onPublishClick={onPublishClick} />
      <main className="mx-auto max-w-7xl py-14">
        <Outlet />
      </main>
    </div>
  );
}
