# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?

From the scenario, I identified three core actions a user should be able to perform:

1. Enter basic owner and pet info (name, species, and how much time the owner has available today).
2. Add and edit pet care tasks, each with a title, a duration in minutes, and a priority.
3. Generate a daily plan and view it with an explanation of why each task was chosen and when it happens.

My initial UML design (in `diagrams/uml.mmd`) has six classes, separated into three roles: classes that hold data, one class that makes decisions, and classes that represent the result.

- **Owner** — holds the owner's name and their main constraint: how many minutes they have available today.
- **Pet** — holds the pet's name and species, and owns the list of care tasks. Tasks are added through an `add_task()` method so any future validation (like rejecting zero-minute tasks) lives in one place.
- **Task** — a single care task: title, duration in minutes, and priority. Pure data, no logic.
- **Scheduler** — the decision-maker. It reads the pet's tasks and the owner's time budget, ranks tasks by priority, keeps the ones that fit in the available time, and produces a DailyPlan. It is stateless (no attributes), so the same inputs always produce the same plan, which makes it easy to test with pytest without touching the Streamlit UI.
- **ScheduledTask** — one entry in the plan: the task, its assigned start time, and a short reason recorded at the moment the Scheduler decided to include it.
- **DailyPlan** — the result: the ordered list of ScheduledTasks plus a list of tasks that were skipped (and why), with an `explain()` method that reads back the stored reasons.

The main idea behind this split is separation of responsibilities: data classes don't make decisions, the Scheduler doesn't store data, and explanations are recorded when decisions are made instead of being reconstructed afterward.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.

Yes. After converting the UML into class stubs, I asked my AI assistant to review the skeleton for missing relationships and logic bottlenecks. Based on that review I made three changes:

1. **Removed the Owner → Pet arrow from the UML.** The review found that the diagram showed "Owner owns Pet" but the code had no such link — the UI holds both objects and passes them separately into `Scheduler.build_plan(owner, pet)`. Since nothing in the code ever needs to reach the pet *through* the owner, I removed the arrow so the diagram matches the real structure instead of keeping a relationship that exists only on paper.

2. **Added a `PRIORITY_ORDER` constant and validation in `add_task()`.** Priority is stored as a string ("high"/"medium"/"low"), and the review pointed out that sorting strings alphabetically gives the wrong order (high < low < medium). I added a module-level mapping (`{"high": 0, "medium": 1, "low": 2}`) that the scheduler will sort by, and made `add_task()` reject tasks with unknown priorities or non-positive durations — the validation now lives in the single doorway that was designed for it.

3. **Added a `SkippedTask` class so skipped tasks keep their reason.** The review flagged that scheduled tasks carried a "why chosen" reason but skipped tasks were a bare list with no "why not." The AI suggested leaving this as-is since there's currently only one skip reason, but I decided the explanation should be symmetric — the plan should explain what it left out just as well as what it included — so I added a small `SkippedTask` dataclass (task + reason) and changed `DailyPlan.skipped` to hold those.

Later, when checking the Task class against the project brief, I made two more adjustments: I moved field validation from `Pet.add_task()` into `Task.__post_init__` so an invalid task (zero duration, unknown priority or frequency) cannot even be constructed, no matter where it comes from — `add_task()` stays as the doorway for list-level rules. I also resolved an ambiguity in the brief on purpose: a task's "time" means its **duration** (the README requires "duration + priority at minimum"), while time-of-day is the *scheduler's output* (`ScheduledTask.start_time`), not a task input.

The biggest design change came from the multi-pet requirement. Earlier I had removed the Owner → Pet link because nothing in the code needed it — but the rubric requires the Owner to manage multiple pets and the Scheduler to read tasks across all of them through one Owner method, not from a single pet. So the relationship came back, stronger than before: `Owner` now holds a list of pets with `add_pet()` and `get_all_tasks()`, and `Scheduler.build_plan(owner)` no longer takes a pet at all — it calls `owner.get_all_tasks()` and never reaches into `owner.pets` directly, so only Owner knows how pets are stored. This was a useful lesson: removing the link was right *for the requirements I had at the time*, and adding it back cleanly was easy precisely because the classes were small and decoupled. I also added `pet_name` to Task (stamped by `Pet.add_task`) so a plan covering several pets can say which task belongs to which pet.

Later I reversed the "time means duration" decision. A task now has an optional `time` of day for fixed appointments (like meds at 09:00), and the scheduler books those at their time and fits flexible tasks into the gaps around them. The first version only stored and validated the field — the scheduler ignored it — and an audit of the project flagged it as "built but not connected", together with `sort_by_time()`, `explain()` and `mark_complete()`, which nothing in the app or demo used. Finishing them added a few more pieces to the design: a `due_date` on Task, `next_occurrence()` and `Pet.complete_task()` for recurring tasks, `Pet.edit_task()` / `remove_task()` and `Owner.remove_pet()` so the app can edit and delete, `Owner.filter_tasks()` so the app can show tasks by completion status or pet, and an `end_time` on ScheduledTask (which also removed a duplicate time helper from `main.py`).

One more finding was noted for implementation time rather than changing the design: start times will be computed as minutes-since-start-of-day (integers) inside the scheduler and only formatted to "HH:MM" strings when creating each `ScheduledTask`, because time arithmetic can't be done on strings.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

The scheduler considers five things, in this order:

1. **Whether the task is owed today** — completed tasks and tasks whose `due_date` is in the future are left out; overdue tasks stay in.
2. **Priority** (high → medium → low) — the owner said they need help with the *important* care first, so this is the main ranking.
3. **Frequency** as a tie-breaker — a daily task skipped today is a missed day, while a weekly one has six more chances.
4. **Duration** as the last tie-breaker — shorter tasks first, so more tasks fit.
5. **The owner's available minutes and fixed times** — the hard limits. A task is only kept if it fits in the time left, a fixed-time task must not overlap another fixed one, and flexible tasks go in the earliest free gap from 08:00.

I put the time budget as a hard limit and priority as the main ranking because those are the two things the scenario names directly ("time available, priority"). Frequency and duration only break ties, so they never let a low-priority task beat a high-priority one.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

The scheduler is **greedy**: it walks down the ranked list and keeps each task that still fits (tasks that didn't fit get one retry at the end, in case a refund freed some minutes), instead of searching for the combination that uses the most minutes. So with 40 minutes, a high-priority 30-minute walk is kept and two medium 20-minute tasks are skipped, even though the two medium tasks would use the full 40 minutes. I think this is the right call here: an owner would rather do the most important thing than the most things, the result is easy to explain ("not enough time left"), and the same input always gives the same plan.

A second tradeoff is how fixed times and the budget interact. Fixed appointments are chosen in rank order like everything else, so a low-priority appointment can be skipped when the budget runs out — but once chosen, a flexible task never pushes an appointment out of its slot, because flexible tasks are placed *after* the appointments are booked. If a flexible task then finds no gap, its minutes are given back rather than wasted. And when two appointments overlap, the scheduler skips the lower-ranked one rather than moving it, because an appointment's time usually can't be changed by the app (a vet call is at 08:15 whether the plan likes it or not).

A third tradeoff is in conflict detection. `detect_conflicts()` checks whether time *ranges* overlap (start + duration), not just whether two tasks start at the same minute — a 17:30 grooming that lasts 45 minutes really does clash with an 18:00 play session. But it only *warns*: it doesn't move either task or ask the owner which to keep, and it compares every pair of tasks (fine for a household's handful of tasks, slow for thousands). Returning warnings instead of raising an error keeps the app running and leaves the decision to the owner, who knows which appointment can move.

A fourth tradeoff is **readability over performance**. The scheduler re-sorts the booked tasks every time a flexible task looks for a gap, and `detect_conflicts()` compares every pair of tasks, so the work grows quickly as tasks are added. Keeping the list sorted with `bisect`, or stopping the pair loop early once tasks no longer overlap, would be faster, but each makes the code harder to read and check. A pet owner has a handful of tasks a day, where the difference can't be measured, so I chose code that is easy to follow and test (see the `build_plan()` review in section 3).

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
- What kinds of prompts or questions were most helpful?

I used an AI coding assistant (Claude Code) throughout the project, but in different roles at different stages:

- **Design review.** After writing the class skeleton, I asked the AI to look for missing relationships and logic bottlenecks. It suggested the `PRIORITY_ORDER` mapping (because sorting the strings "high/medium/low" alphabetically gives the wrong order), pointed out that my UML showed an Owner → Pet link the code didn't have, and flagged that skipped tasks had no reason attached (see section 1b).
- **Building a terminal demo.** The AI wrote `main.py`, a script that builds an owner with two pets and eight tasks and prints the plan, so I could check the scheduler before touching the Streamlit UI.
- **Checking my work against the brief.** I pasted the assignment's requirements for `main.py` and asked the AI to assess them *critically*. It confirmed all four were met but warned that "tasks with different times" is ambiguous: my tasks have different *durations*, but a grader might expect different *times of day*. It also noticed that the old starter code's `Task` had a `due_time` field, which hinted at what the course originally meant.
- **Readability.** I asked for a clearer terminal format. The AI suggested an aligned table with start–end times, a separate "Skipped" section, and a one-line summary, and explained the trade-off: the per-task reasons disappear from the table, so it added a single "Why this order" line instead.
- **Sorting logic.** For `Scheduler.sort_by_time()` I asked the AI how to sort my `Task` objects by their `time` attribute, and specifically how to use a lambda function as the `key` to `sorted()` for strings in `"HH:MM"` format. It suggested `sorted(tasks, key=lambda t: (t.time is None, t.time or ""))`: the first part of the tuple is `False` for timed tasks and `True` for flexible ones, and since `False < True` the timed tasks come first; the second part then orders them by clock time. It explained that comparing the strings directly is only safe because `Task` rejects anything that isn't zero-padded (`"09:00" < "10:00"` works, but `"9:00"` would sort after `"10:00"`), and that `sorted()` is stable, so flexible tasks keep the order they were added in. I kept that design and verified it with three tests, including one that crosses the 9 → 10 o'clock boundary.
- **Recurring tasks and `timedelta`.** The brief says a completed daily task's next copy is due *today + 1 day*. My first version counted from the task's *due date* instead, which gives the same answer for a task due today but not for an overdue one: finishing a walk that was due three days ago booked the next walk for two days ago, so it was overdue again straight away. I asked the AI how to use Python's `timedelta` to compute the next date accurately. It explained that `date + timedelta(days=1)` does real calendar arithmetic, so month ends, year ends and leap days roll over correctly (Oct 31 → Nov 1, Dec 31 → Jan 1, Feb 28 → Feb 29 in 2028) — something adding 1 to a day number or editing a date string would get wrong. The fix counts from the day the task is completed (`date.today()` by default), and `mark_complete()` now creates the next copy itself, so the logic lives in `Task`. One case needed a decision: if a task is finished *early* (tomorrow's walk done today), counting from today would book tomorrow again, so in that case it counts from the due date. The completion date can also be passed in, so tests don't depend on the real calendar; tests cover the overdue case, early completion, and the month, year and leap-day rollovers.
- **Simplifying `build_plan()`.** I shared the scheduler's main method with the AI and asked: "How could this algorithm be simplified for better readability or performance?" It pointed out that the same block — try to book the task, add it to Skipped with the reason if that fails, otherwise take its minutes off the budget — was written out in two of the three passes (and almost again in the second), each with its own temporary `problem` variable. It suggested three changes:
  1. *Readability:* move that block into a small helper, `_book_or_skip()`, that returns True if the task was booked. Each pass then reads as one `if`/`elif` per case.
  2. *More "Pythonic":* use the walrus operator (`if (problem := self._try_book(...)):`) or build the lists with comprehensions. This is shorter, but the budget changes after every task, so a comprehension would hide the step-by-step logic that makes the plan explainable.
  3. *Performance:* keep the booked list sorted with `bisect.insort` instead of re-sorting it every time a flexible task looks for a gap. Faster in theory, but more code to understand, and with fewer than 20 tasks a day the difference can't be measured.

  I kept only the first. It removed the duplication without making the method cleverer, and I rejected the other two because they make the code harder for a person to follow for no real gain at this size. To check that nothing changed, all 106 tests still passed, the `main.py` output was identical before and after, and the app behaved the same.
- **Tests and documentation.** The AI wrote the pytest suite, added one-line summary docstrings to every method, and filled in the README with real output from the demo and the tests.
- **Auditing and finishing the project.** Near the end I asked the AI to read the whole folder and list what was incomplete or "implemented but not connected". It found features that existed only in the backend (fixed times, `sort_by_time()`, `explain()`, `mark_complete()`, recurrence), missing edit/delete in the app, and README sections that no longer matched the code. I then asked it to implement them and bring the README and this reflection up to date.

The most helpful prompts were the ones that asked the AI to **check or explain** rather than just produce: "verify if this script does all the required tasks — assess critically", "what is this for?" about a file it created, and "explain what this instruction means before doing anything". Those answers taught me something and gave me a reason to agree or disagree, instead of just handing me code.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

**What I accepted, changed, or rejected**

- **Rejected: leaving skipped tasks without a reason.** During the design review, the AI suggested keeping `DailyPlan.skipped` as a plain list because there was only one possible skip reason. I disagreed — the plan should explain what it left out just as clearly as what it included — so I added the `SkippedTask` class. That turned out to matter: the plan now says exactly why a task was dropped ("needs 45 min, only 5 min remaining"), and a test checks for it.
- **Stopped and redirected: the test suite.** I asked for a test file, and the AI went ahead and wrote 14 tests before I had given it the assignment's actual requirements. I told it to wait, then gave it the two required tests (task completion and task addition) and asked whether they existed. The addition test was already there, but the completion test only set `task.completed = True` directly, because `Task` had no `mark_complete()` method. The AI offered two options — add the method, or test the field — and I chose to add `mark_complete()` so the test matches the assignment's wording. I kept the extra scheduler tests after checking what each one covers.
- **Questioned before accepting: `pytest.ini`.** The AI added this file without me asking for it. Instead of accepting it blindly, I asked what it was for. It explained that without `pythonpath = .`, pytest can't import `pawpal_system.py` from inside the `tests/` folder — and I had seen that exact `ModuleNotFoundError` happen before the file was added — so I kept it.
- **Chose the less literal option: docstrings.** The instruction said "1-line docstrings". The AI pointed out that most of my methods already had longer docstrings explaining design decisions, and offered either cutting them to one line or keeping them but making the first line a standalone summary. I chose the second, because the longer explanations (like why daily tasks rank above weekly ones) support this reflection.
- **Accepted:** the `PRIORITY_ORDER` mapping, the terminal table format, and the README updates — after checking each one.
- **Caught a design flaw during implementation: appointments vs. flexible tasks.** The first version of fixed-time scheduling placed every task in rank order, so a high-priority flexible walk could take 08:00–08:30 and then knock a lower-priority 08:15 vet call out as a "conflict" — even though the walk could simply have moved. The fix was to choose tasks and book appointments first, then fit the flexible tasks into the gaps. A test (`test_flexible_task_never_pushes_out_a_fixed_task`) now guards against it coming back.
- **Fixed two leftover quirks after a second audit.** A flexible task that found no free slot kept its minutes reserved, so that time was lost to every task after it — now the minutes are refunded and tasks that didn't fit get a second try. And each entry's reason said "fits in the N min remaining" as of when the task was *chosen*, so the numbers jumped around in the clock-ordered table (an 08:30 task could show more time left than a 07:00 one). Reasons are now written after the plan is final, in clock order, as "40/90 min used after this", so they rise steadily down the plan.

**How I verified the results**

- **Ran the code, not just read it.** I ran `python main.py` after every change and checked the schedule by hand. At that stage (before fixed times were added), the two 10-minute feedings came first, the completed "Heartworm pill" was missing, the 85 minutes used stayed under the 90 available, and the two low-priority weekly tasks were skipped because only 5 minutes were left.
- **Ran the tests.** `pytest` passed all 17 tests at that point, including the two required ones (the suite has since grown to 109 — see section 4). When the AI changed docstrings, I re-ran the tests to make sure no code had changed by accident.
- **Checked requirements line by line.** For `main.py`, I compared the script against each item in the assignment instead of assuming "it runs" meant "it's done". I did the same for the sorting and filtering step, and it caught a real gap: `sort_by_time()` and `filter_tasks()` were implemented, tested and used in the app, but `main.py` never called them, and only one demo task had a fixed time, so there was nothing out of order to sort. I gave four tasks fixed times added out of clock order (17:00, 07:30, 18:00, 08:15) and made the demo print the tasks as added, sorted, and filtered by pet and status before the schedule. (Later, for conflict detection, Grooming moved to 17:30 and Nail trim got 18:00 — the same time as Play session — so the demo also shows two tasks at the same time and the warning it prints.)
- **Asked the AI to prove its claims.** When it said every method had a docstring, it ran a script that listed any function without one (none were missing) instead of me taking its word for it. When it updated the README, I asked it to use only output that actually exists today and leave the unfinished parts (like the Streamlit walkthrough) as placeholders, so the README doesn't describe features I haven't built.
- **Debugged a failing test run.** When I changed recurring tasks to count from today, six tests failed. Asking "is the bug in my test code or my `pawpal_system.py` logic?" showed it was the tests: they used a fixed date (`TODAY = 2026-10-21`) while the new code counted from the real date (2026-10-23), so the expected dates were two days off. The fix was to let `mark_complete()` take the completion date and pass `TODAY` in the tests, so they don't depend on the calendar. I reran `python -m pytest` until everything passed.
- **Kept the UML in sync.** When `mark_complete()` was added to `Task`, I made sure it was added to `diagrams/uml.mmd` too, so the diagram still matches the code.

The biggest lesson: the AI is fast and usually right, but it will sometimes do more than I asked or make choices I didn't make. Asking "what is this for?" and "does this actually meet the requirement?" kept me in charge of the design.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

There are 109 tests in two files.

`tests/test_pawpal.py` (87 tests) checks the logic layer directly:

- **Task basics** — tasks can't be created with a bad duration, priority, frequency or time; `mark_complete()` flips the status and returns the next occurrence; adding a task stamps the pet's name.
- **Ranking and budget** — priority order, the daily-before-weekly and shortest-first tie-breaks, never going over the available minutes, a smaller task still fitting after a bigger one is skipped, and skipped tasks carrying a reason.
- **Fixed times** — appointments booked at their time, flexible tasks filling gaps around them, a flexible task never pushing out an appointment, overlapping appointments (the higher-ranked one wins), back-to-back appointments *not* counting as a conflict, appointments using up the budget, a task running past midnight, refunding the minutes of a flexible task that finds no gap, entries coming back in clock order with a rising "min used" total, and skipped tasks listed in rank order.
- **Conflict detection** — `detect_conflicts()` warning about overlaps for the same pet and for different pets, identical start times, two same-time tasks that both fit the budget (a warning and a skip, not a crash), every pair when three tasks overlap, *no* warning for touching ends, flexible, completed or other-day tasks, an empty list instead of an error, and the plan warning about clashes even when both tasks were skipped for lack of time, or when an overdue task clashes with today's.
- **Recurrence** — `mark_complete()` and `next_occurrence()` creating the next daily or weekly task due today + 1 or 7 days (including for an overdue task, a task finished early, and dates that cross a month end, year end or leap day), `complete_task()` booking the next one, tomorrow's task staying out of today's plan, and overdue tasks still being planned.
- **Filtering** — `filter_tasks()` by completion status, by pet name, and both together, a pet with no tasks, results being the owner's real tasks (so marking one complete sticks), and a completed recurring task appearing as done while its next copy appears as to do.
- **Editing** — the duplicate-task rule, `edit_task()` changing fields in place, a bad edit leaving the task untouched, and removing tasks and pets.

`tests/test_app.py` (22 tests) runs the Streamlit app headlessly with `AppTest`, fills in the forms and clicks the buttons — adding pets and tasks, error messages, Mark complete, Delete, Edit, Remove pet, the pet and status filters, conflict warnings, and generating a schedule.

The scheduler tests matter most because the schedule is the whole point of the app, and its rules interact (budget, priority, fixed times) in ways that are easy to get wrong — the appointment bug in section 3b is an example. The app tests matter because a feature that works in the backend is no use if the button isn't wired to it; that's exactly the "built but not connected" problem the project had before.

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

Fairly confident for the cases the app lets a user create: every rule in the scheduler has at least one test, the tests check exact output (titles and start times) rather than just "something was returned", and the `main.py` demo is small enough to check by hand — the 07:30 Morning walk and 08:15 Vet call keep their slots, the 17:30 Grooming and the 18:00 Play session and Nail trim are skipped because only 10 minutes are left (and flagged as three clashing pairs, one of them at exactly the same time), Mochi's Feeding moves to 08:30 because the 5-minute gap before the call is too short, and 80 of the 90 minutes are used.

Edge cases I would test next:

- A fixed-time task that was over budget on the first look, gets a second try, and then clashes with a flexible task placed in the meantime.
- An appointment that starts before 08:00 and runs past it, overlapping the first flexible slot.
- An available time of 0 minutes.
- Editing a task's frequency after it has been completed, and completing the same recurring task several days in a row.
- Very long plans, to check the explanation text stays readable in the app.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
