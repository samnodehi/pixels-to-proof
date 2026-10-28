# Demo script — draft v3 (narrator style; for Sam's approval before any audio is generated)

Voice: "daniel" (ElevenLabs eleven-v4 via OpenRouter), calm storyteller, short pauses at "—" and line breaks.
Spoken text ≈ 410 words: ≈ 2:45 at 150 words per minute, ≈ 2:56 at 140 (to be measured on the generated audio; cut further if it runs over 2:55). Burned-in English captions, one short line at a time.
Screen: the live Space (recorded runs), plus close-ups of receipts and the ledger. Every number below comes from the
recorded runs in `showcase/` (beetle and peacock on commit 49f237b; breadth on 7cf697a; faults on 49f237b).

---

**0:00 — The hook** *(screen: a results paragraph, its numbers lighting up one by one)*
Every scientific paper makes promises.
Beetle larvae leave the ground at almost half a metre per second.
Male peacock spiders take off at twenty-five degrees.
Often the journal also publishes the data behind them — the tables, even the videos.
But does anyone check one against the other? Almost never. So we built an agent that does.

**0:20 — Meet Pixels to Proof** *(screen: the bundle of files going into the Space; header "Hands-off")*
You give it exactly what the journal published. Nothing more.
Muse Spark reads it all and drafts a plan: what each file and column means, and every number the paper claims.
Then code checks every single proposal against the files.
The rule is simple: the model may propose — but no number in a verdict is ever written by a language model.

**0:45 — Watching it think** *(screen: ledger view, "MUSE SPARK PROPOSED" lines next to "CODE CHECKED" ✔/✘)*
Every step lands in a ledger — what the model proposed, and the check that accepted or rejected it.
A quote that isn't really in the paper? Rejected — and Muse Spark is asked again, with the reason.

**1:00 — Numbers versus data** *(screen: peacock claims table; then the Breadth tab)*
Take the peacock spider paper.
Its take-off angles only add up as circular means — exactly the statistics the authors said they used.
Three of its printed values turn out to be the table's numbers cut short, not rounded.
Across thirteen papers — athletes, fish, ants, birds, spiders. Three hundred and nineteen printed numbers.
Sixty-three reproduce to the printed digit. For every other one, it tells you why not.

**1:30 — When there's video** *(screen: beetle receipt playing, then the green verdict card)*
When there's a video, it goes all the way down to physics.
In the beetle paper, it rejects eleven of twelve shots up front — no scale, or a camera too slow.
One jump is left. SAM 3.1 tracks it, the agent finds its row in the data blind, from the jump's shape alone — and the
published take-off speed holds up. Reproduced.

**1:55 — Knowing when to say no** *(screen: the spider receipt, the amber refusal card)*
The spider video is trickier. The agent splits recordings that fade into each other, reads "playback four times
faster", and measures the gap to the target.
Then it refuses. The flight isn't a clean arc — something slows the spider down, almost straight against its motion —
the mark of air drag on a tiny body.
An honest "I can't measure this" beats a confident wrong number.

**2:25 — Can it be fooled?** *(screen: Calibration tab, the fault table)*
We tried. Twelve kinds of deliberately wrong model answers.
Four were caught, six the agent repaired on its own, two changed nothing — and not one produced a wrong verdict.

**2:40 — Close** *(screen: title card)*
Muse Spark proposes. SAM 3.1 tracks. Code checks every step, and writes it down.
Pixels to Proof — a second reader for the numbers in science.
