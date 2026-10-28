# Demo script — draft v2 (for Sam's approval before any audio is generated)

Voice: "daniel" (ElevenLabs eleven-v4 via OpenRouter). About 370 words, ~2:40 at 140 words per minute.
Screen: the live Space (recorded runs), plus close-ups of receipts and the ledger. Every number below comes from the
recorded runs in `showcase/` (beetle and peacock on commit 49f237b; breadth on 7cf697a; faults on 49f237b).

---

**0:00 — The problem** *(screen: a paper's results paragraph, numbers highlighted)*
A scientific paper is a list of numbers. Today most journals also publish the data behind those numbers — and often
the videos. Almost nobody checks one against the other. Pixels to Proof does, on its own.

**0:15 — What it is** *(screen: the bundle of files → the Space header "Hands-off")*
Give it only what the journal published: the PDF, the data tables, the scripts, the videos. Muse Spark reads everything
and proposes an audit plan — which file is which, what every column means, every number the paper claims. Code checks
each proposal against the files. No number in a verdict is written by a language model.

**0:40 — The agent at work** *(screen: ledger view, purple "MUSE SPARK PROPOSED" next to "CODE CHECKED" ✔/✘)*
Every proposal is a line in the ledger, next to the check that accepted or rejected it. A quote that is not in the
paper is rejected, and Muse Spark is asked again with the reason. When it says a number covers only the males, code
first checks that the table has those rows.

**1:05 — Numbers against data** *(screen: peacock claims table, then the Breadth tab)*
In a peacock-spider paper, the take-off angles reproduce only as circular means — exactly the statistics the authors
used. Three printed values are the table's values truncated, not rounded. Across thirteen papers — athletes, fish,
ants, birds, spiders — the agent checked 319 printed numbers. Sixty-three reproduce to the last printed digit; for
every other one, it says why it could not.

**1:35 — Where there is video** *(screen: beetle receipt video, verdict card; then the spider receipt)*
Where there is a video, it goes further. In a beetle-larva paper it refuses eleven of twelve shots — real-time
footage, no scale — before tracking anything. One jump is tracked by SAM 3.1, matched to its row of the data table
blind, from geometry alone, and the published take-off speed is reproduced. In the spider video it splits recordings
joined by dissolves, reads "playback four times faster", measures the gap to the landing target — and refuses: the
flight is not ballistic, and the extra deceleration points against the motion, as air drag would.

**2:15 — Can it be fooled?** *(screen: Calibration tab, fault table)*
We fed it twelve kinds of wrong model answers: wrong units, wrong frame rates, a box on the background. Four were
caught, six were repaired by the agent itself, two changed nothing. None produced a wrong verdict.

**2:35 — Close** *(screen: title card)*
Muse Spark proposes. SAM 3.1 tracks. Code checks every step and writes it down.
Pixels to Proof — a second reader for the numbers in science.
