import { Link } from "@tanstack/react-router";
import { useState } from "react";

import { LicenceStatus, PhraseFrame, ProvenanceTag } from "@/components/domain";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useAuth } from "@/features/auth/AuthProvider";

import type { LandingCopy, MoveId } from "./copy.en";
import { DEFAULT_MOVE, MOVE_FRAMES, type MoveFrame } from "./frames";
import { GRID, idx, Wrap } from "./layout";

/** The slot inside the headline: a live phrase set where a word would be. */
function Slot({ text }: { text: string }) {
  return (
    <span
      aria-hidden
      className="mx-[0.06em] inline-flex h-[0.95em] w-[4.7em] items-center justify-center align-[-0.1em] bg-[var(--slot-bg)] text-[var(--slot)]"
    >
      <span key={text} className="slot-in font-serif text-[0.6em] font-normal tracking-normal">{text}</span>
    </span>
  );
}

/** A real library entry, built from the app's own components, that follows the selected move. */
function EntryPreview({ copy, active, move }: { copy: LandingCopy; active: MoveFrame; move: MoveId }) {
  const p = copy.hero.preview;
  return (
    <aside aria-label={p.label} className="reveal lg:col-span-5" style={idx(2)}>
      <div data-ui className="flex flex-col gap-6 bg-white p-7 text-base">
        <div className="flex items-center justify-between gap-4 text-sm text-neutral-600">
          <span>{p.crumb[move]}</span>
          <Badge variant="success">{p.status}</Badge>
        </div>
        <PhraseFrame key={move} frame={active.frame} className="slot-in text-[22px] leading-[1.45]" />
        <dl className="flex flex-col gap-2.5">
          <dt className="text-sm text-neutral-600">{p.slotsLabel}</dt>
          {active.slots.map((slot) => (
            <dd key={slot.name} className="flex items-baseline justify-between gap-6">
              <span className="text-neutral-600">{slot.name}</span>
              <span className="text-right">{slot.example}</span>
            </dd>
          ))}
        </dl>
        <div className="flex flex-col gap-1.5">
          <span className="text-sm text-neutral-600">{p.contractLabel}</span>
          <p>{p.contracts[move]}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceTag value="authored" />
          <LicenceStatus status="cleared" />
          <Badge variant="secondary">{copy.hero.strengthLabel}: {copy.hero.strengths[active.strength]}</Badge>
        </div>
      </div>
      <p className="mt-3 text-sm text-[var(--muted)]">{p.caption}</p>
    </aside>
  );
}

export function Hero({ copy }: { copy: LandingCopy }) {
  const { client } = useAuth();
  const [move, setMove] = useState<MoveId>(DEFAULT_MOVE);
  const active = MOVE_FRAMES.find((m) => m.id === move) ?? MOVE_FRAMES[0];

  return (
    <section data-chapter="paper" className="bg-[var(--paper)] pb-28 pt-40">
      <Wrap className={`${GRID} items-center`}>
        <div className="lg:col-span-7">
          <h1 aria-label={copy.hero.titleLabel} className="display reveal text-[clamp(40px,4.9vw,76px)]">
            <span aria-hidden className="block whitespace-nowrap">{copy.hero.titleParts.before} <Slot text={active.slot} /></span>
            <span aria-hidden className="block">{copy.hero.titleParts.after}</span>
          </h1>
          <p className="reveal mt-8 max-w-[34rem] text-[20px] leading-[1.5]" style={idx(1)}>{copy.hero.sentence}</p>
          <div className="reveal mt-8 flex flex-wrap items-center gap-x-8 gap-y-5" style={idx(2)}>
            <ToggleGroup
              type="single"
              value={move}
              onValueChange={(value) => value && setMove(value as MoveId)}
              aria-label={copy.hero.moveGroupLabel}
              spacing={1}
            >
              {MOVE_FRAMES.map((m) => (
                <ToggleGroupItem
                  key={m.id}
                  value={m.id}
                  className="press h-11 rounded-none bg-black/[0.07] px-5 text-base hover:bg-black/[0.12] data-[state=on]:bg-[#176b8f] data-[state=on]:text-white"
                >
                  {copy.hero.moves[m.id]}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="reveal mt-8" style={idx(3)}>
            <Button asChild size="xl" className="press rounded-none">
              {client ? (
                <Link to="/phrasebank">{copy.hero.action}</Link>
              ) : (
                <Link to="/signin" search={{ next: "/phrasebank" }}>{copy.hero.action}</Link>
              )}
            </Button>
          </div>
        </div>
        <EntryPreview copy={copy} active={active} move={move} />
      </Wrap>
    </section>
  );
}
