import { Link } from "@tanstack/react-router";
import type { CSSProperties } from "react";

import { LicenceStatus, PhraseFrame, ProvenanceTag } from "@/components/domain";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/features/auth/AuthProvider";

import artOfPrinting from "./assets/art-of-printing-1732.jpg";
import cardCatalog from "./assets/card-catalog.jpg";
import compositors from "./assets/compositors-1899.jpg";
import letterpressPoster from "./assets/letterpress-loop-poster.jpg";
import letterpressLoop from "./assets/letterpress-loop.webm";
import readingRoom from "./assets/reading-room-1859.jpg";
import platesA from "./assets/transactions-1665-a.jpg";
import platesB from "./assets/transactions-1665-b.jpg";
import type { LandingCopy } from "./copy.en";
import { SHOWCASE_FRAME } from "./frames";

// The clip fades from and to black at its ends; loop only the lit part so a panel is never a black screen.
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
      className="treat absolute inset-0 h-full w-full object-cover"
    />
  );
}

const idx = (i: number) => ({ "--i": i }) as CSSProperties;

export function Intro({ copy }: { copy: LandingCopy }) {
  return (
    <section data-chapter="paper" className="relative min-h-[110svh] px-[var(--margin)] pb-24 pt-[34svh]">
      <div className="max-w-[48rem]">
        <h2 className="display reveal text-[clamp(48px,5.4vw,84px)]">{copy.intro.heading}</h2>
        <p className="reveal mt-10 max-w-[34rem] text-[22px] leading-[1.45]" style={idx(1)}>{copy.intro.text}</p>
      </div>
      <img
        src={platesA}
        alt={copy.intro.imageAlt}
        width={1600}
        height={2206}
        loading="lazy"
        className="treat reveal absolute right-0 top-[10svh] w-[38vw] object-cover"
        style={idx(2)}
      />
      <img
        src={compositors}
        alt={copy.intro.smallImageAlt}
        width={1600}
        height={1285}
        loading="lazy"
        className="treat reveal mt-16 w-[24vw] object-cover"
        style={idx(3)}
      />
    </section>
  );
}

export function Showcase({ copy }: { copy: LandingCopy }) {
  const { lines, activeIndex, card } = copy.showcase;
  return (
    <section data-chapter="ink" className="relative overflow-hidden bg-[var(--dark)] px-[var(--margin)] py-40 text-[var(--paper)]">
      <div className="relative" style={{ fontSize: "clamp(72px, 9vw, 150px)" }}>
        {lines.map((line, i) =>
          i === activeIndex ? (
            <h2 key={line} className="display reveal whitespace-nowrap text-[var(--paper)]" style={idx(i)}>{line}</h2>
          ) : (
            <p key={line} aria-hidden className="display reveal whitespace-nowrap text-[var(--muted-dark)]" style={idx(i)}>{line}</p>
          ),
        )}
        <div
          data-ui
          className="reveal absolute right-0 top-4 z-10 w-[min(40vw,34rem)] -rotate-3 bg-white p-6 text-base shadow-none"
          style={{ ...idx(2), fontSize: "16px" }}
        >
          <div className="mb-4 flex items-center justify-between text-sm text-neutral-600">
            <span>{card.move}: {card.moveValue}</span>
            <span>{card.strength}: {card.strengthValue}</span>
          </div>
          <PhraseFrame frame={SHOWCASE_FRAME} className="text-[22px]" />
          <div className="mt-5 flex flex-wrap gap-2">
            <ProvenanceTag value="authored" />
            <LicenceStatus status="cleared" />
          </div>
        </div>
      </div>
      <div className="ml-auto mt-16 flex w-5/12 flex-col gap-5 text-[22px] leading-[1.5]">
        <h3 className="display reveal text-[22px]">{copy.showcase.heading}</h3>
        {copy.showcase.paragraphs.map((p, i) => (
          <p key={p} className="reveal" style={idx(i + 1)}>{p}</p>
        ))}
      </div>
    </section>
  );
}

const HOW_IMAGES = [readingRoom, null, cardCatalog, artOfPrinting];

export function How({ copy }: { copy: LandingCopy }) {
  return (
    <section id="how" data-chapter="ink" aria-labelledby="how-title" className="bg-[var(--dark)] text-[var(--paper)]">
      <h2 id="how-title" className="sr-only">{copy.how.heading}</h2>
      {copy.how.steps.map((step, i) => (
        <div key={step.verb} className="relative h-svh min-h-[640px] snap-start overflow-hidden">
          <div className="absolute inset-0">
          {HOW_IMAGES[i] ? (
            <img
              src={HOW_IMAGES[i] as string}
              alt={step.imageAlt}
              width={1600}
              height={1200}
              loading="lazy"
              className="treat settle absolute inset-0 h-full w-full object-cover"
            />
          ) : (
            <LoopVideo label={step.imageAlt} />
          )}
          <div className="absolute inset-0 bg-black/50" />
          <h3 className="display reveal absolute inset-0 grid place-items-center text-[clamp(96px,15vw,260px)] text-[var(--paper)]">{step.verb}</h3>
          <p className="reveal absolute bottom-12 left-[var(--margin)] max-w-[30rem] bg-black/60 p-5 text-[17px] leading-snug text-[var(--paper)]" style={idx(2)}>{step.text}</p>
          </div>
        </div>
      ))}
    </section>
  );
}

export function Start({ copy }: { copy: LandingCopy }) {
  return (
    <section id="start" data-chapter="paper" className="px-[var(--margin)] py-40">
      <h2 className="display reveal max-w-[60rem] pl-[3vw] text-[clamp(48px,5.4vw,84px)]">{copy.start.heading}</h2>
      <div className="mt-24 grid grid-cols-12 gap-x-6">
        <img
          src={platesB}
          alt={copy.start.imageAlt}
          width={1600}
          height={2206}
          loading="lazy"
          className="treat reveal col-span-3 self-end object-cover"
          style={idx(2)}
        />
        <table className="reveal col-span-5 col-start-8 w-full text-[17px]" style={idx(1)}>
          <caption className="sr-only">{copy.start.tableLabel}</caption>
          <tbody>
            {copy.start.rows.map((row, i) => (
              <tr key={row.name} className={i === 4 ? "[&>*]:pt-11" : undefined}>
                <th scope="row" className="py-[13px] pr-4 text-left align-top font-semibold">
                  <Link to={row.to} aria-label={row.linkLabel} className="press">{row.name}</Link>
                </th>
                <td className="py-[13px] pr-4 align-top leading-snug">{row.text}</td>
                <td className="py-[13px] text-right align-top" aria-hidden>→</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
  return (
    <section id="questions" data-chapter="ink" className="bg-[var(--dark)] px-[var(--margin)] py-40 text-[var(--paper)]">
      <h2 className="display reveal text-[clamp(48px,5.4vw,84px)]">{copy.faq.heading}</h2>
      <div className="mt-20 grid grid-cols-12 gap-x-6">
        <div className="col-span-8 col-start-5 flex flex-col gap-9">
          {copy.faq.items.map((item, i) => (
            <details key={item.q} className="reveal group -mx-6 px-6 py-3 open:bg-[var(--dark-tile)]" style={idx(i % 3)}>
              <summary className="press flex cursor-pointer items-center justify-between gap-6 py-2 text-[22px]">
                {item.q}
                <Chevron />
              </summary>
              <p className="mt-3 max-w-[48ch] pb-3 text-[17px] leading-[1.55]">{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Cta({ copy }: { copy: LandingCopy }) {
  const { client } = useAuth();
  return (
    <section data-chapter="paper" className="relative h-svh min-h-[720px] bg-[var(--paper)]">
      <h2 className="display reveal flex h-full flex-col items-center justify-between px-[var(--margin)] py-10 text-center text-[clamp(72px,9vw,150px)] leading-none">
        <span>{copy.cta.lineOne}</span>
        <span>{copy.cta.lineTwo}</span>
      </h2>
      <div className="pointer-events-none absolute inset-0 grid place-items-center">
        <div className="pointer-events-auto flex flex-col items-center gap-4">
          <div className="reveal relative flex items-center gap-[120px]" style={idx(1)}>
            <Button asChild size="xl" className="press w-[260px] rounded-none">
              {client ? (
                <Link to="/phrasebank">{copy.cta.browse}</Link>
              ) : (
                <Link to="/signin" search={{ next: "/phrasebank" }}>{copy.cta.browse}</Link>
              )}
            </Button>
            <span className="absolute left-1/2 -translate-x-1/2 text-base">{copy.cta.or}</span>
            <Button asChild size="xl" variant="secondary" className="press w-[260px] rounded-none">
              <Link to="/writer">{copy.cta.write}</Link>
            </Button>
          </div>
          <p className="reveal text-[17px]" style={idx(2)}>{copy.cta.note}</p>
        </div>
      </div>
    </section>
  );
}

export function Footer({ copy }: { copy: LandingCopy }) {
  return (
    <footer data-chapter="ink" className="relative h-svh min-h-[760px] overflow-hidden bg-[var(--dark)] px-[var(--margin)] pt-40 text-[var(--paper)]">
      <div className="grid grid-cols-12 gap-x-6">
        <div className="col-span-7">
          <h2 className="display reveal text-[clamp(48px,5.4vw,84px)]">{copy.footer.invitation}</h2>
          <div className="reveal mt-8" style={idx(1)}>
            <Button asChild size="xl" className="press rounded-none">
              <Link to="/signin">{copy.footer.action}</Link>
            </Button>
          </div>
        </div>
        <nav className="reveal col-span-3 col-start-10 flex flex-col gap-3 text-base" style={idx(1)} aria-label={copy.nav.label}>
          {copy.footer.links.map((link) => (
            <Link key={link.href} to={link.href} className="press w-fit">{link.label}</Link>
          ))}
        </nav>
      </div>
      <div className="absolute inset-x-[var(--margin)] bottom-[calc(19vw*0.7+20px)] flex flex-col gap-3 text-sm">
        <p>
          {copy.footer.picturesLabel}:{" "}
          {copy.credits.map((c, i) => (
            <span key={c.href}>
              <a href={c.href} className="underline underline-offset-2">{c.title}</a>{c.creator ? `, ${c.creator}` : ""}{c.licence !== "public domain" ? `, ${c.licence}` : ""}
              {i < copy.credits.length - 1 ? "; " : "."}
            </span>
          ))}
        </p>
        <p className="flex justify-between">
          <span>{copy.footer.rights}</span>
          <span>{copy.footer.provenance}</span>
        </p>
      </div>
      <p aria-hidden className="display absolute bottom-0 left-[var(--margin)] translate-y-[30%] whitespace-nowrap text-[19vw] leading-none text-[var(--paper)]">
        {copy.footer.wordmark}
      </p>
    </footer>
  );
}
