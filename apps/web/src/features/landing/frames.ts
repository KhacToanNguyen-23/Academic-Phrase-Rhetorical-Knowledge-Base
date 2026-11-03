import type { MoveId } from "./copy.en";

// Self-authored sample frames for the hero. They are academic English content and are not translated.
// The gap and finding frames follow the style of the backend seed patterns; method and limitation are written here.
export interface MoveFrame {
  id: MoveId;
  /** Short phrase shown inside the headline slot. */
  slot: string;
  /** Full frame shown under the move selector. */
  frame: string;
  strength: "hedged" | "neutral";
}

export const MOVE_FRAMES: MoveFrame[] = [
  { id: "gap", slot: "remains unclear", frame: "The role of {topic} in {context} remains unclear.", strength: "hedged" },
  { id: "method", slot: "was measured", frame: "{variable} was measured with {instrument} at {interval}.", strength: "neutral" },
  { id: "finding", slot: "suggests that", frame: "These findings suggest that {factor} may contribute to {outcome}.", strength: "hedged" },
  { id: "limitation", slot: "may not hold", frame: "These results may not hold for {population} outside {setting}.", strength: "hedged" },
];

export const DEFAULT_MOVE: MoveId = "finding";

export const SHOWCASE_FRAME = "These findings suggest that {factor} may contribute to {outcome} under {condition}.";
