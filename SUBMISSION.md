# Submission text (draft, for the Cerebral Valley submission page)

The form's exact fields were not visible before submission opened; the parts below cover the usual ones. Every number
is from the recorded runs in `showcase/` (see README "At a glance").

**Project name:** Pixels to Proof

**Tagline:** An agent that checks the numbers in a scientific paper against the paper's own data and videos.

**Track:** Indie Developer · **Problem statement:** Push the Frontier (science) · **Bonus:** Best Agentic Use-Case

**Links:** repository `github.com/samnodehi/pixels-to-proof` · live app `huggingface.co/spaces/SamNo/pixels-to-proof`
· demo video (2:52) `youtu.be/1L_HC-seEo8`

## Description

Journals now publish the data behind a paper — tables, and sometimes high-speed videos — but almost nobody checks a
paper's printed numbers against them. Pixels to Proof does. You give it exactly what the journal published, nothing
more. Muse Spark 1.3 reads everything and proposes a plan: what each file and table column means, every kinematic
number the paper claims, what is printed on each video. Code checks every proposal; rejected ones go back to Muse Spark
with the reason. Statistics are recomputed from the paper's own table, by arithmetic only. When a video is usable,
SAM 3.1 tracks the animal, the agent finds the matching row of the data blind, from the jump's shape alone, and
re-measures the take-off speed from physics, with self-checks on gravity and free flight.

On 13 papers audited hands-off, 63 of 319 printed numbers reproduce to the printed digit, and every other one gets a
named reason. It recognises angles that only add up as circular means, and values printed truncated instead of rounded. One
beetle-larva jump is re-measured and REPRODUCED; two peacock-spider jumps are refused because the flights are not
ballistic; for the male, the extra acceleration points against the motion, as air drag would. Twelve kinds of deliberately wrong model answers produced no
wrong verdict.

## How we used Meta's models

- **Muse Spark 1.3** (Responses API, Files API for PDFs, strict JSON-schema output) does all the reading: the paper
  with digests of its tables and scripts, contact sheets of each video shot (to split recordings joined by dissolves),
  and single frames (printed frame rate, playback speed, scale reference, the animal's box). Its answers are proposals
  that code checks field by field; rejected fields go back to Muse Spark with the checker's reasons.
- **SAM 3.1** tracks the animal in the high-speed clip, prompted with Muse Spark's box (a text concept as fallback); when a track
  fails its quality gate, Muse Spark proposes a new box with the rejection reason.
- Every model output and every check is written to a run ledger that the app shows step by step.

## What was built during the hackathon

All of it: the repository's first commit is from 2026-10-27. The only adapted code is the SAM 3.1 streaming adapter
from Meta's model cookbook (MIT). The papers, videos and tables are third-party works under CC BY 4.0 / CC0, credited
in the app. The demo narration is an AI voice (ElevenLabs via OpenRouter).

## Challenges

Real papers with a usable high-speed video, a visible scale, a stated frame rate and a per-jump table are rare, so the
agent had to be just as useful without video: checking printed numbers against tables works on many more papers.
Model answers vary between runs, so nothing a model says reaches a verdict without a code check.

## What's next

More table layouts (several blocks in one sheet), montage videos split by the agent, and a batch mode for journals and
reviewers to run on new submissions.

## Video upload (YouTube, unlisted)

**Title:** Pixels to Proof — checking a paper's numbers against its own data (Meta AI Developer Hackathon 2026)

**Description:**

Pixels to Proof is an agent that checks the motion numbers in a scientific paper against the paper's own published
data and videos. Muse Spark 1.3 reads the paper and proposes; code checks every proposal; SAM 3.1 tracks the animal;
no number in a verdict is written by a language model. Built during the Meta Global AI Developer Hackathon,
Oct 27 – Nov 4, 2026.

Code: https://github.com/samnodehi/pixels-to-proof
Live app: https://huggingface.co/spaces/SamNo/pixels-to-proof

Paper media shown (all openly licensed):
- Bertone M.A. et al. (2022). A novel power-amplified jumping behavior in larval beetles. PLOS ONE 17(1): e0256509.
  https://doi.org/10.1371/journal.pone.0256509 (CC BY 4.0)
- Narendra A. et al. (2025). Sexual dimorphism in jump kinematics and choreography in peacock spiders. J Exp Biol 228(3):
  jeb249416. https://doi.org/10.1242/jeb.249416 (CC BY 4.0); video https://doi.org/10.5281/zenodo.13208287
  (CC BY 4.0); data https://doi.org/10.5061/dryad.hdr7sqvsp (CC0)

Narration: AI voice (ElevenLabs, via OpenRouter).
