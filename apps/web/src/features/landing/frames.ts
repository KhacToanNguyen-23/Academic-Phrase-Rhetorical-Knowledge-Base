import type { MoveId } from "./copy.en";

// Self-authored sample frames. They are academic English content and are not translated.
// The gap and finding frames follow the style of the backend seed patterns; method and limitation are written here.
export interface MoveFrame {
  id: MoveId;
  /** Short phrase shown inside the headline slot. */
  slot: string;
  /** Full frame shown in the product preview. */
  frame: string;
  strength: "hedged" | "neutral";
  /** Example values for each slot, as the writer would fill them. */
  slots: { name: string; example: string }[];
}

export const MOVE_FRAMES: MoveFrame[] = [
  {
    id: "gap",
    slot: "remains unclear",
    frame: "The role of {topic} in {context} remains unclear.",
    strength: "hedged",
    slots: [
      { name: "topic", example: "language models" },
      { name: "context", example: "higher education" },
    ],
  },
  {
    id: "method",
    slot: "was measured",
    frame: "{variable} was measured with {instrument} at {interval}.",
    strength: "neutral",
    slots: [
      { name: "variable", example: "Sleep duration" },
      { name: "instrument", example: "a wrist-worn actigraph" },
      { name: "interval", example: "30-second epochs" },
    ],
  },
  {
    id: "finding",
    slot: "suggests that",
    frame: "These findings suggest that {factor} may contribute to {outcome}.",
    strength: "hedged",
    slots: [
      { name: "factor", example: "sleep consolidation" },
      { name: "outcome", example: "memory retention" },
    ],
  },
  {
    id: "limitation",
    slot: "may not hold",
    frame: "These results may not hold for {population} outside {setting}.",
    strength: "hedged",
    slots: [
      { name: "population", example: "adult learners" },
      { name: "setting", example: "the study site" },
    ],
  },
];

export const DEFAULT_MOVE: MoveId = "finding";

/** A published sentence and the frame lifted from it (the intro section). */
export const LIFT_FRAME = "These findings suggest that {factor} may contribute to {outcome} under {condition}.";
