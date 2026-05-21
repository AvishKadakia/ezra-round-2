import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { Blocks } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type TopNavProps = {
  searchValue: string;
  onSearchChange: (value: string) => void;
  onPublishClick: () => void;
};

const navItems = [
  { label: "Gallery", href: "/" },
  // { label: "Reviews", href: "/reviews" },
  // { label: "Shared", href: "/shared" },
  // { label: "MCP", href: "/mcp" },
];

export function TopNav({ searchValue, onSearchChange, onPublishClick }: TopNavProps) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <header className="sticky top-5 z-40 mx-auto flex max-w-7xl items-center gap-8 rounded-2xl border bg-white/90 px-7 py-5 shadow-soft backdrop-blur">
      <Link to="/" className="flex shrink-0 items-center gap-3">
        <Blocks className="h-7 w-7 text-slate-950" />
        <span className="text-2xl font-semibold tracking-tight text-slate-950">Artifact Hub</span>
      </Link>

      <nav className="hidden items-center gap-9 md:flex">
        {navItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            className={({ isActive }) =>
              cn(
                "text-base font-medium text-slate-500 transition-colors hover:text-slate-950",
                (isActive || (item.href === "/" && location.pathname === "/")) && "border-b-2 border-slate-950 pb-2 text-slate-950",
              )
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-5">
        <Input
          value={searchValue}
          placeholder="Search"
          className="hidden w-48 origin-right transition-[width] duration-300 focus:w-[min(460px,42vw)] md:block"
          onChange={(event) => {
            onSearchChange(event.target.value);
            if (location.pathname !== "/") navigate("/");
          }}
        />
        <Button className="rounded-xl px-8" onClick={onPublishClick}>Publish</Button>
      </div>
    </header>
  );
}
