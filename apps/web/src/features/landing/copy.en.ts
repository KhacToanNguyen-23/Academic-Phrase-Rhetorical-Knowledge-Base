// Every visible string of the landing page lives here, typed as LandingCopy.
// To add Vietnamese later: create copy.vi.ts with the same type and pass it to <LandingPage copy={...} />.
// Phrase frames themselves (frames.ts) are academic English content and stay the same in every locale.

export type MoveId = "gap" | "method" | "finding" | "limitation";

export interface LandingCopy {
  lang: string;
  brand: string;
  nav: { how: string; start: string; questions: string; signIn: string; label: string };
  hero: {
    titleParts: { before: string; after: string };
    titleLabel: string;
    sentence: string;
    moveGroupLabel: string;
    moves: Record<MoveId, string>;
    strengthLabel: string;
    strengths: Record<"hedged" | "neutral", string>;
    action: string;
  };
  intro: { heading: string; text: string; imageAlt: string; smallImageAlt: string };
  showcase: {
    lines: [string, string, string, string];
    activeIndex: number;
    heading: string;
    paragraphs: [string, string];
    card: { move: string; moveValue: string; strength: string; strengthValue: string; provenance: string; licence: string };
  };
  how: {
    heading: string;
    steps: { verb: string; text: string; imageAlt: string }[];
  };
  start: {
    heading: string;
    tableLabel: string;
    openLabel: string;
    rows: { name: string; text: string; to: "/library" | "/phrasebank" | "/vocabulary" | "/journals" | "/writer" | "/inbox"; linkLabel: string }[];
    imageAlt: string;
  };
  faq: { heading: string; items: { q: string; a: string }[] };
  cta: { lineOne: string; lineTwo: string; browse: string; write: string; or: string; note: string };
  footer: {
    invitation: string;
    action: string;
    links: { label: string; href: "/writer" | "/phrasebank" | "/vocabulary" }[];
    rights: string;
    provenance: string;
    picturesLabel: string;
    wordmark: string;
  };
  credits: { title: string; creator: string; licence: string; href: string }[];
}

export const copyEn: LandingCopy = {
  lang: "en",
  brand: "Academic Wordbank",
  nav: { how: "How it works", start: "Where to start", questions: "Questions", signIn: "Sign in", label: "Page sections" },
  hero: {
    titleParts: { before: "The right", after: "for every claim" },
    titleLabel: "The right phrase for every claim",
    sentence: "Academic Wordbank is a phrasebank and academic vocabulary dictionary, built from licensed journal articles.",
    moveGroupLabel: "Rhetorical move",
    moves: { gap: "Gap", method: "Method", finding: "Finding", limitation: "Limitation" },
    strengthLabel: "Claim strength",
    strengths: { hedged: "hedged", neutral: "neutral" },
    action: "Open the phrasebank",
  },
  intro: {
    heading: "Phrases with the slots left open",
    text: "A phrase frame keeps the structure of a published sentence and lifts out its content, leaving slots for your own claim.",
    imageAlt: "An engraved plate of microscope figures from the Philosophical Transactions of the Royal Society, 1805",
    smallImageAlt: "Compositors setting type in a printing shop, 1899",
  },
  showcase: {
    lines: ["Introduction", "Methods", "Results", "Discussion"],
    activeIndex: 2,
    heading: "Every phrase belongs to a move",
    paragraphs: [
      "A pattern records more than its words: the rhetorical move it serves, the slots it leaves open, how strongly it commits to a claim, and where it came from.",
      "A pattern whose licence is unknown stays locked. It is not recommended until someone with the right to decide has cleared it.",
    ],
    card: {
      move: "Move",
      moveValue: "Finding",
      strength: "Claim strength",
      strengthValue: "Hedged",
      provenance: "Authored",
      licence: "Licence cleared",
    },
  },
  how: {
    heading: "How a phrase reaches the bank",
    steps: [
      { verb: "Import", text: "Only articles whose licence allows mining are read.", imageAlt: "The domed reading room of the British Museum, engraving, 1859" },
      { verb: "Mine", text: "Sentences are split into frames, with their content lifted into slots.", imageAlt: "A letterpress printing a sheet, in a short film clip" },
      { verb: "Review", text: "Two rounds of human review decide what enters the bank.", imageAlt: "A wooden card catalogue cabinet" },
      { verb: "Recommend", text: "A writer gets the approved frames that fit the claim and its evidence.", imageAlt: "The Art and Mystery of Printing Emblematically Displayed, engraving, 1732" },
    ],
  },
  start: {
    heading: "Where each kind of phrase lives",
    tableLabel: "Screens",
    openLabel: "Open",
    rows: [
      { name: "Library", text: "Approved patterns with their slots, usage contract and provenance", to: "/library", linkLabel: "Open the library" },
      { name: "Phrasebank", text: "A browsable reference collection, kept apart from the bank", to: "/phrasebank", linkLabel: "Open the phrasebank" },
      { name: "Vocabulary", text: "Academic words by lemma, word family and rank", to: "/vocabulary", linkLabel: "Open the vocabulary list" },
      { name: "Journals", text: "Verified guidelines apart from phrasing observed in the corpus", to: "/journals", linkLabel: "Open the journal profiles" },
      { name: "Writer", text: "Draft a sentence and check it against your evidence", to: "/writer", linkLabel: "Open the writer" },
      { name: "Review", text: "Submissions waiting for an editor", to: "/inbox", linkLabel: "Open the inbox" },
    ],
    imageAlt: "A second engraved plate from the Philosophical Transactions of the Royal Society, 1805",
  },
  faq: {
    heading: "Where the phrases come from",
    items: [
      {
        q: "Is this the Academic Phrasebank?",
        a: "No. The patterns in the bank are self-authored or used with permission. The phrasebank browser shows a separate reference collection, clearly marked, that never enters recommendations.",
      },
      {
        q: "Why is an entry locked?",
        a: "When a pattern's licence or provenance is unknown, the bank fails closed: the entry is shown as locked and is not recommended until the rights are cleared.",
      },
      {
        q: "What is a slot?",
        a: "A slot is the part of a phrase frame you fill with your own content, such as the finding or the method. The frame supplies the structure and you supply the claim.",
      },
      {
        q: "How is a journal's own phrasing found?",
        a: "Licensed articles from a journal are mined for sentence frames. Frames that recur in that journal are put in front of editors before they appear beside the base phrasebank.",
      },
      {
        q: "Can the writer invent a citation?",
        a: "No. The writer checks a sentence against the evidence you give it and flags unsupported numbers, DOIs and citations instead of filling them in.",
      },
      {
        q: "Who approves a phrase?",
        a: "People do. A pattern enters the bank after two rounds of review, and every version is kept: an approved version is never edited in place.",
      },
    ],
  },
  cta: {
    lineOne: "Read the bank,",
    lineTwo: "or write with it?",
    browse: "Browse the phrasebank",
    write: "Open the writer",
    or: "or",
    note: "Browsing needs a staff key. The writer is open to everyone.",
  },
  footer: {
    invitation: "Find the phrase your journal uses",
    action: "Staff sign in",
    links: [
      { label: "Writer", href: "/writer" },
      { label: "Phrasebank", href: "/phrasebank" },
      { label: "Vocabulary", href: "/vocabulary" },
    ],
    rights: "© 2026 Academic Wordbank",
    provenance: "Patterns are self-authored or used with permission.",
    picturesLabel: "Pictures",
    wordmark: "wordbank",
  },
  credits: [
    {
      title: "Printing in a letterpress (film)",
      creator: "Subhashish Panigrahi",
      licence: "CC BY-SA 4.0",
      href: "https://commons.wikimedia.org/wiki/File:Printing_in_a_letterpress.webm",
    },
    {
      title: "Philosophical Transactions plates",
      creator: "",
      licence: "public domain",
      href: "https://commons.wikimedia.org/wiki/File:The_Philosophical_transactions_of_the_Royal_society_of_London,_from_their_commencement_in_1665,_in_the_year_1800_BHL23269244.jpg",
    },
    {
      title: "British Museum reading room",
      creator: "",
      licence: "public domain",
      href: "https://commons.wikimedia.org/wiki/File:Reading-room_of_the_British_Museum_LCCN2007682650.jpg",
    },
    {
      title: "Compositors at work",
      creator: "",
      licence: "public domain",
      href: "https://commons.wikimedia.org/wiki/File:Compositors_working_in_printing_shop,_Hampton_Institute,_Hampton,_Virginia_LCCN94502417.jpg",
    },
    {
      title: "Card catalogue cabinet",
      creator: "MarkBuckawicki",
      licence: "CC0",
      href: "https://commons.wikimedia.org/wiki/File:Wooden_Card_Catalog_Furniture.jpg",
    },
    {
      title: "The Art and Mystery of Printing",
      creator: "",
      licence: "public domain",
      href: "https://commons.wikimedia.org/wiki/File:The_Art_and_Mystery_of_Printing_Emblematically_Displayed_(BM_1868,0808.10094_1).jpg",
    },
  ],
};
