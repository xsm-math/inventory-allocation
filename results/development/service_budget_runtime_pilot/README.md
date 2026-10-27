# Incomplete runtime development pilot

This directory is development evidence, not a completed validation or held-out
test study. Prototype source is pinned at commit `a05f122`; `protocol.json` records
its intended 120-episode design. The process was stopped after 45 fully completed
policy episodes to investigate primary optimality precision and refinement costs.
An active incomplete episode/group was discarded. No test paths were inspected.
All seeds 30001–30004 were then designated runtime development seeds, and the final
study uses fresh validation seeds 31001–31004. Original test seeds remain untouched.

The prototype requested zero relative primary gap with the native solver's default
absolute tolerance. A separate 42-day surge probe on already inspected seed 30001
used service tolerance 0.02 and the reference network's default planning penalty 8,
not the main factorial control's penalty 32. This diagnostic path is deliberately
not presented as a comparable performance replication of the factorial experiment.
Its daily primary incumbent/lower-bound gaps were at most 0.000678 deficit units
(0.0678 percentage point), yet primary status remained unproven on 21 days. Mean
decision solve time was 1.1202 seconds.

After explicitly setting primary absolute precision to 0.001 deficit units
(0.1 percentage point), a repeated probe on that same development path had maximum
reported primary bound gap 0.000986 and zero precision-unmet days. Mean decision
solve time was 0.5340 seconds. This is a single-path runtime diagnostic, not a
general speed or out-of-sample quality claim. Final held-out results must assess
the modified controller separately. It is not exact primary optimality.

Files preserve the incomplete progress table, source/input fingerprints, original
and repaired probe daily ledgers and the precision-repair metadata. HiGHS emitted
a repeated native diagnostic string during some solves; this logging behavior is
documented in [upstream issue #2783](https://github.com/ERGO-Code/HiGHS/issues/2783).
Feasibility is independently checked and status/bound fields drive diagnostics;
log strings are not treated as pass/fail evidence.
