import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { useAuth } from "@/features/auth/AuthProvider";

import { ADMIN_ITEM, HOME, NAV_GROUPS } from "./nav";

/** Cmd/Ctrl+K: jump to a screen by name. Screens only; no search endpoint is involved. */
export function CommandMenu() {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { client } = useAuth();

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const groups = [
    ...(client ? [{ label: "Workspace", items: [HOME] }] : []),
    ...NAV_GROUPS.map((group) => ({ ...group, items: group.items.filter((item) => client || item.publicAccess) })),
    ...(client?.role === "admin" ? [{ label: "Admin", items: [ADMIN_ITEM] }] : []),
  ].filter((group) => group.items.length > 0);

  return (
    <CommandDialog open={open} onOpenChange={setOpen} title="Go to screen" description="Type a screen name, then press Enter.">
      <Command>
      <CommandInput placeholder="Go to screen…" />
      <CommandList>
        <CommandEmpty>No screen with that name.</CommandEmpty>
        {groups.map((group) => (
          <CommandGroup key={group.label} heading={group.label}>
            {group.items.map((item) => (
              <CommandItem
                key={item.to}
                value={item.label}
                onSelect={() => {
                  setOpen(false);
                  void navigate({ to: item.to });
                }}
              >
                <item.icon strokeWidth={1.5} />
                {item.label}
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
      </CommandList>
      </Command>
    </CommandDialog>
  );
}
