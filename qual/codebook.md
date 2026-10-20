# Codebook (version 3.1)

This is the codebook the two coders used for the 120 meeting passages. It asks three
questions about each passage. For each question, read the choices in order and pick the
first one that fits. Use only what the passage says. If you would have to guess, pick
Neither.

The nine practice passages with their answers and reasons are in `practice.csv`.

## 1. Topic: what is the passage about?

Go down the list and stop at the first yes.

| Choice | Use when the passage is about |
|---|---|
| Ownership | Who should do something from now on: who gets alerts, who triages or fixes, a role or group, a policy, a response deadline, how vulnerabilities are reported or published |
| People | What contributors read, learn, or get credit for: training, written guidelines, contributor levels, badges, leaderboards, bounties |
| Tools | Something software runs: a scanner, dashboard, alert, pull-request bot, automated check, or release signing |
| Other | Anything else: plans, milestones, schedules, the funder, product features |

## 2. Action: was something done or decided?

Go down the list and stop at the first yes.

| Choice | Use when |
|---|---|
| Decided | The group settles what to do: someone states a decision, or one person proposes and another agrees |
| Done | Someone reports work finished, switched on, or a number reached |
| Neither | Everything else: ideas, questions, problems, plans, work still in progress |

## 3. Effect: does the passage say something made the work harder or easier?

| Choice | Use when |
|---|---|
| Neither | Nothing is said to slow or help the work, or you would have to guess |
| Barrier: tool trouble | A tool gave wrong or noisy results, or something it should send never arrived |
| Barrier: burden or fit | It would add work for volunteers or go against how the community works |
| Barrier: too many repos | The number of repos or modules limits what can be done |
| Barrier: no owner or no time | Nobody is assigned, the right person is missing, or the person has had no time |
| Barrier: other | Any other barrier (say what it is in the note column) |
| Enabler: builds on existing | It uses something already there: an existing workflow, tool feature, or community structure |
| Enabler: outside example | It leans on a known standard, an outside audit, or how another project does it |
| Enabler: other | Any other enabler (say what it is in the note column) |

If a passage shows both a barrier and an enabler, code the barrier.

## Procedure

1. Read this codebook and the practice passages with their answers.
2. Code every passage: one topic, one action, and one effect.
3. Use the note column when unsure, and always when choosing an "other".
4. Work alone. Do not compare with the other coder until both have finished.
