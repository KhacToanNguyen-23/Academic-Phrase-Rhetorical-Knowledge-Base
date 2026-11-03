import { Link } from "@tanstack/react-router";

import { PhraseFrame } from "@/components/domain";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";

import artOfPrinting from "./assets/art-of-printing-1732.jpg";
import cardCatalog from "./assets/card-catalog.jpg";
import letterpressPoster from "./assets/letterpress-loop-poster.jpg";
import letterpressLoop from "./assets/letterpress-loop.webm";
import readingRoom from "./assets/reading-room-1859.jpg";
import type { LandingCopy } from "./copy.en";
import { LIFT_FRAME, MOVE_FRAMES } from "./frames";
import { GRID, idx, SECTION, SectionHead, Wrap } from "./layout";

/** A published sentence becomes a frame: the product's one idea, shown with its own components. */
export function Intro({ copy }: { copy: LandingCopy }) {
  const c = copy.intro;
  return (
    <section data-chapter="paper" className={`${SECTION} bg-[var(--paper-2)]`}>
      <Wrap className={GRID}>
        <SectionHead title={c.heading}>
          <p>{c.text}</p>
        </SectionHead>
        <div className="reveal lg:col-span-7" style={idx(2)}>
          <div data-ui className="flex flex-col gap-8 bg-white p-8 text-base">
            <div className="flex flex-col gap-3">
              <span className="text-sm text-neutral-600">{c.publishedLabel}</span>
              <p className="font-serif text-[22px] leading-[1.45]">
                {c.published.map((part, i) =>
                  part.lifted ? (
                    <span key={i} className="bg-neutral-200 px-1 text-neutral-700">{part.text}</span>
                  ) : (
                    <span key={i}>{part.text}</span>
                  ),
                )}
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <span className="text-sm text-neutral-600">{c.frameLabel}</span>
              <PhraseFrame frame={LIFT_FRAME} className="text-[22px] leading-[1.45]" />
            </div>
          </div>
          <p className="mt-3 text-sm text-[var(--muted)]">{c.caption}</p>
        </div>
      </Wrap>
    </section>
  );
}

/** The four IMRaD sections, each with the move it uses. */
export function Showcase({ copy }: { copy: LandingCopy }) {
  const c = copy.showcase;
  return (
    <section data-chapter="ink" className={`${SECTION} bg-[var(--dark)] text-[var(--paper)]`}>
      <Wrap className={GRID}>
        <SectionHead title={c.heading} sticky>
          {c.paragraphs.map((p) => (
            <p key={p}>{p}</p>
          ))}
        </SectionHead>
        <ol className="flex flex-col gap-10 lg:col-span-7">
          {c.rows.map((row, i) => {
            const frame = MOVE_FRAMES.find((m) => m.id === row.move) ?? MOVE_FRAMES[0];
            return (
              <li key={row.section} className="reveal grid gap-x-8 gap-y-2 md:grid-cols-[10rem_1fr]" style={idx(i % 3)}>
                <h3 className="text-[20px] font-semibold">{row.section}</h3>
                <div className="flex flex-col gap-2">
                  <PhraseFrame frame={frame.frame} className="text-[22px] leading-[1.45]" />
                  <span className="text-base text-[var(--muted-dark)]">
                    {copy.hero.moves[row.move]} · {copy.hero.strengths[frame.strength]}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      </Wrap>
    </section>
  );
}

const HOW_IMAGES = [readingRoom, null, cardCatalog, artOfPrinting];

// The clip fades from and to black at its ends; loop only the lit part so the frame is never black.
const CLIP_START = 1.5;
const CLIP_END = 25;

function LoopVideo({ label }: { label: string }) {
  return (
    <video
      src={letterpressLoop}
      poster={letterpressPoster}
      aria-label={label}
      autoPlay
      muted
      playsInline
      preload="auto"
      onLoadedMetadata={(e) => {
        e.currentTarget.currentTime = CLIP_START;
      }}
      onTimeUpdate={(e) => {
        if (e.currentTarget.currentTime >= CLIP_END) e.currentTarget.currentTime = CLIP_START;
      }}
      onEnded={(e) => {
        e.currentTarget.currentTime = CLIP_START;
        void e.currentTarget.play();
      }}
      className="treat h-full w-full object-cover"
    />
  );
}

export function How({ copy }: { copy: LandingCopy }) {
  const c = copy.how;
  return (
    <section id="how" data-chapter="paper" className={`${SECTION} bg-[var(--paper)]`}>
      <Wrap className={GRID}>
        <SectionHead title={c.heading} sticky>
          <p>{c.text}</p>
        </SectionHead>
        <ol className="flex flex-col gap-14 lg:col-span-7">
          {c.steps.map((step, i) => (
            <li key={step.verb} className="reveal grid items-center gap-x-8 gap-y-5 md:grid-cols-5" style={idx(i % 2)}>
              <div className="aspect-[4/3] overflow-hidden bg-black/10 md:col-span-2">
                {HOW_IMAGES[i] ? (
                  <img src={HOW_IMAGES[i] as string} alt={step.imageAlt} width={1600} height={1200} loading="lazy" className="treat h-full w-full object-cover" />
                ) : (
                  <LoopVideo label={step.imageAlt} />
                )}
              </div>
              <div className="flex flex-col gap-3 md:col-span-3">
                <h3 className="display text-[28px]">{step.verb}</h3>
                <p className="max-w-[28rem] text-[20px] leading-[1.5]">{step.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </Wrap>
    </section>
  );
}

export function Start({ copy }: { copy: LandingCopy }) {
  const c = copy.start;
  return (
    <section id="start" data-chapter="paper" className={`${SECTION} bg-[var(--paper-2)]`}>
      <Wrap className={GRID}>
        <SectionHead title={c.heading}>
          <p>{c.text}</p>
        </SectionHead>
        <table className="reveal w-full text-[17px] lg:col-span-7" style={idx(2)}>
          <caption className="sr-only">{c.tableLabel}</caption>
          <tbody>
            {c.rows.map((row) => (
              <tr key={row.name}>
                <th scope="row" className="w-[9.5rem] py-3.5 pr-6 text-left align-top font-semibold">
                  <Link to={row.to} aria-label={row.linkLabel} className="press">{row.name}</Link>
                </th>
                <td className="py-3.5 pr-6 align-top leading-snug">{row.text}</td>
                <td className="py-3.5 text-right align-top" aria-hidden>→</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Wrap>
    </section>
  );
}

function Chevron() {
  return (
    <svg className="chev shrink-0" width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="m4 7 6 6 6-6" />
    </svg>
  );
}

export function Faq({ copy }: { copy: LandingCopy }) {
  const c = copy.faq;
  return (
    <section id="questions" data-chapter="paper" className={`${SECTION} bg-[var(--paper)]`}>
      <Wrap className={GRID}>
        <SectionHead title={c.heading} sticky>
          <p>{c.text}</p>
        </SectionHead>
        <div className="flex flex-col gap-2 lg:col-span-7">
          {c.items.map((item, i) => (
            <details key={item.q} className="reveal -mx-5 px-5 py-2 open:bg-[var(--paper-2)]" style={idx(i % 3)}>
              <summary className="press flex cursor-pointer items-center justify-between gap-6 py-3 text-[20px] font-medium">
                {item.q}
                <Chevron />
              </summary>
              <p className="max-w-[48ch] pb-4 text-[17px] leading-[1.55]">{item.a}</p>
            </details>
          ))}
        </div>
      </Wrap>
    </section>
  );
}

/** Closing choice and footer on one dark ground. */
export function CtaFooter({ copy }: { copy: LandingCopy }) {
  const { client } = useAuth();
  const c = copy.cta;
  const f = copy.footer;
  return (
    <footer data-chapter="ink" className="bg-[var(--dark)] pt-28 text-[var(--paper)]">
      <Wrap className={GRID}>
        <div className="lg:col-span-5">
          <h2 className="display reveal text-[clamp(30px,2.9vw,42px)]">{c.heading}</h2>
          <p className="reveal mt-5 max-w-[26rem] text-[20px] leading-[1.5]" style={idx(1)}>{c.text}</p>
        </div>
        <div className="reveal flex flex-wrap items-start gap-4 lg:col-span-7" style={idx(2)}>
          <Button asChild size="xl" className="press rounded-none">
            {client ? <Link to="/phrasebank">{c.browse}</Link> : <Link to="/signin" search={{ next: "/phrasebank" }}>{c.browse}</Link>}
          </Button>
          <Button asChild size="xl" variant="secondary" className="press rounded-none">
            <Link to="/writer">{c.write}</Link>
          </Button>
        </div>
      </Wrap>
      <Wrap className="mt-28 flex flex-col gap-4 pb-12 text-sm">
        <nav aria-label={copy.nav.label} className="flex flex-wrap gap-x-8 gap-y-2 text-base">
          {f.links.map((link) => (
            <Link key={link.href} to={link.href} className="press">{link.label}</Link>
          ))}
          <Link to="/signin" className="press">{c.signIn}</Link>
        </nav>
        <p className="max-w-[72rem] leading-relaxed text-[var(--muted-dark)]">
          {f.picturesLabel}:{" "}
          {copy.credits.map((credit, i) => (
            <span key={credit.href}>
              <a href={credit.href} className="underline underline-offset-2">{credit.title}</a>
              {credit.creator ? `, ${credit.creator}` : ""}
              {credit.licence !== "public domain" ? `, ${credit.licence}` : ""}
              {i < copy.credits.length - 1 ? "; " : "."}
            </span>
          ))}
        </p>
        <p className="flex flex-wrap justify-between gap-x-8 gap-y-1 text-[var(--muted-dark)]">
          <span>{f.rights}</span>
          <span>{f.provenance}</span>
        </p>
      </Wrap>
    </footer>
  );
}
