import { Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";

import { BrandMark } from "@/app/BrandMark";

import { copyEn, type LandingCopy } from "./copy.en";
import { Hero } from "./Hero";
import { Wrap } from "./layout";
import { CtaFooter, Faq, How, Intro, Showcase, Start } from "./Sections";
import "./landing.css";

type Ink = "paper" | "ink";

/** The header takes the ink of the chapter under it (colour by chapter). */
function Header({ copy, ink }: { copy: LandingCopy; ink: Ink }) {
  return (
    <header
      className="fixed inset-x-0 top-0 z-50 transition-colors duration-300"
      style={{ color: ink === "paper" ? "var(--ink)" : "var(--paper)", backgroundColor: ink === "paper" ? "var(--paper)" : "var(--dark)" }}
    >
      <Wrap className="flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-xl font-semibold tracking-tight" aria-label={copy.brand}>
          <BrandMark />
          {copy.brand}
        </Link>
        <nav aria-label={copy.nav.label} className="flex items-center gap-8 text-base">
          <a href="#how" className="press hidden md:inline">{copy.nav.how}</a>
          <a href="#start" className="press hidden md:inline">{copy.nav.start}</a>
          <a href="#questions" className="press hidden md:inline">{copy.nav.questions}</a>
          <Link to="/signin" className="press font-medium">{copy.nav.signIn}</Link>
        </nav>
      </Wrap>
    </header>
  );
}

export function LandingPage({ copy = copyEn }: { copy?: LandingCopy }) {
  const root = useRef<HTMLDivElement>(null);
  const [ink, setInk] = useState<Ink>("paper");

  useEffect(() => {
    const previousLang = document.documentElement.lang;
    document.documentElement.lang = copy.lang;
    return () => {
      document.documentElement.lang = previousLang;
    };
  }, [copy.lang]);

  useEffect(() => {
    const el = root.current;
    if (!el) return;
    el.classList.add("js");

    const seen = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).dataset.in = "true";
            seen.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.15 },
    );
    el.querySelectorAll(".reveal, .settle").forEach((node) => seen.observe(node));

    // A chapter becomes "current" when its top edge passes the header band.
    const chapters = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setInk((entry.target as HTMLElement).dataset.chapter === "ink" ? "ink" : "paper");
        }
      },
      { rootMargin: "0px 0px -92% 0px" },
    );
    el.querySelectorAll("[data-chapter]").forEach((node) => chapters.observe(node));

    return () => {
      seen.disconnect();
      chapters.disconnect();
    };
  }, []);

  return (
    <div ref={root} className="landing min-h-svh">
      <Header copy={copy} ink={ink} />
      <main id="main">
        <Hero copy={copy} />
        <Intro copy={copy} />
        <Showcase copy={copy} />
        <How copy={copy} />
        <Start copy={copy} />
        <Faq copy={copy} />
      </main>
      <CtaFooter copy={copy} />
    </div>
  );
}
