"use client";

import { useEffect, useState } from "react";

const SENTENCES = [
  "Rank a mutation. Cite the evidence.",
  "Repurposed drugs, ranked and cited.",
  "When nothing matches, we say so.",
  "An unmatched mutation, queued — not dead.",
];

const TYPE_MS = 45;
const DELETE_MS = 18;
const HOLD_MS = 1800;
const PAUSE_MS = 400;
// Stop deleting once only this many characters remain, then clear the rest
// in one step — avoids a lone letter (e.g. "W") sitting alone on screen.
const DELETE_FLOOR = 6;

export default function CyclingHeadline() {
  const [text, setText] = useState("");
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    if (reduced) {
      setText(SENTENCES[0]);
      return;
    }

    let tid: ReturnType<typeof setTimeout>;
    let sentenceIndex = 0;

    function typeSentence(charIndex: number) {
      const sentence = SENTENCES[sentenceIndex];
      setText(sentence.slice(0, charIndex));
      if (charIndex < sentence.length) {
        tid = setTimeout(() => typeSentence(charIndex + 1), TYPE_MS);
      } else {
        tid = setTimeout(() => deleteSentence(sentence.length), HOLD_MS);
      }
    }

    function deleteSentence(charIndex: number) {
      const sentence = SENTENCES[sentenceIndex];
      if (charIndex <= DELETE_FLOOR) {
        setText("");
        sentenceIndex = (sentenceIndex + 1) % SENTENCES.length;
        tid = setTimeout(() => typeSentence(0), PAUSE_MS);
        return;
      }
      setText(sentence.slice(0, charIndex));
      tid = setTimeout(() => deleteSentence(charIndex - 1), DELETE_MS);
    }

    typeSentence(0);
    return () => clearTimeout(tid);
  }, [reduced]);

  return (
    <h1 className="min-h-[2.4em] text-4xl md:text-5xl font-[var(--font-manrope)] font-extrabold leading-[1.1] tracking-tight text-neutral-heading">
      {text}
      <span className="cursor-blink text-neutral-muted ml-[2px]" />
    </h1>
  );
}
