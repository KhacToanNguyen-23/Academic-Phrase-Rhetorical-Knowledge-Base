import { Link } from "@tanstack/react-router";
import { useState, type CSSProperties } from "react";

import { PhraseFrame } from "@/components/domain";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { useAuth } from "@/features/auth/AuthProvider";

import type { LandingCopy, MoveId } from "./copy.en";
import { DEFAULT_MOVE, MOVE_FRAMES } from "./frames";

/** The slot inside the headline: a live phrase set where a word would be. */
function Slot({ text }: { text: string }) {
  return (
    <span
      aria-hidden
      className="mx-[0.06em] inline-flex h-[0.9em] w-[4.9em] items-center justify-center align-[-0.08em] bg-[var(--slot-bg)] text-[var(--slot)]"
    >
      <span key={text} className="slot-in font-serif text-[0.6em] font-normal tracking-normal">{text}</span>
    </span>
  );
}

export function Hero({ copy }: { copy: LandingCopy }) {
  const { client } = useAuth();
  const [move, setMove] = useState<MoveId>(DEFAULT_MOVE);
  const active = MOVE_FRAMES.find((m) => m.id === move) ?? MOVE_FRAMES[0];

  const title = (
    <>
      <span className="block whitespace-nowrap">{copy.hero.titleParts.before} <Slot text={active.slot} /></span>
      <span className="block whitespace-nowrap">{copy.hero.titleParts.after}</span>
    </>
  );

  return (
    <section
      data-chapter="paper"
      className="relative h-svh min-h-[720px] overflow-hidden"
      style={{ "--hl": "clamp(72px, 7.6vw, 124px)" } as CSSProperties}
    >
      <div className="absolute inset-x-0 top-0 h-1/2 bg-[var(--paper)]" />
      <div className="absolute inset-x-0 bottom-0 h-1/2 bg-[var(--dark)]" />

      {/* Two copies of the headline inside one h1, each clipped to its side of the seam, so the ink changes where it crosses. */}
      <div className="absolute inset-x-0 top-1/2 z-30 -translate-y-[calc(50%+0.32em)] px-[var(--margin)]" style={{ fontSize: "var(--hl)" }}>
        <h1 aria-label={copy.hero.titleLabel} className="display reveal grid place-items-center text-center">
          <span aria-hidden className="col-start-1 row-start-1 text-[var(--ink)]" style={{ clipPath: "inset(0 0 33.2% 0)" }}>
            {title}
          </span>
          <span
            aria-hidden
            className="on-dark pointer-events-none col-start-1 row-start-1 text-[var(--paper)]"
            style={{ clipPath: "inset(66.8% 0 0 0)" }}
          >
            {title}
          </span>
        </h1>
      </div>

      <div
        className="on-dark absolute inset-x-0 bottom-0 top-1/2 z-20 flex flex-col items-center gap-5 px-[var(--margin)] pb-12 text-center text-[var(--paper)]"
        style={{ paddingTop: "calc(var(--hl) * 0.63 + 2.25rem)" }}
      >
        <p className="reveal max-w-[76ch] text-[22px] leading-snug text-balance" style={{ "--i": 1 } as CSSProperties}>{copy.hero.sentence}</p>
        <div className="reveal flex flex-col items-center gap-3" style={{ "--i": 2 } as CSSProperties}>
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
                className="press h-11 rounded-none bg-white/10 px-5 text-base text-[var(--paper)] hover:bg-white/20 hover:text-[var(--paper)] data-[state=on]:bg-[#176b8f] data-[state=on]:text-white"
              >
                {copy.hero.moves[m.id]}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <p className="flex items-baseline gap-4 text-base" aria-live="polite">
            <PhraseFrame frame={active.frame} className="text-[22px]" />
            <span className="text-[var(--muted-dark)]">{copy.hero.strengthLabel}: {copy.hero.strengths[active.strength]}</span>
          </p>
        </div>
        <div className="reveal" style={{ "--i": 3 } as CSSProperties}>
          <Button asChild size="xl" className="press rounded-none">
            {client ? (
              <Link to="/phrasebank">{copy.hero.action}</Link>
            ) : (
              <Link to="/signin" search={{ next: "/phrasebank" }}>{copy.hero.action}</Link>
            )}
          </Button>
        </div>
      </div>
    </section>
  );
}
