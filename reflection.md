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

One more finding was noted for implementation time rather than changing the design: start times will be computed as minutes-since-start-of-day (integers) inside the scheduler and only formatted to "HH:MM" strings when creating each `ScheduledTask`, because time arithmetic can't be done on strings.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
- How did you decide which constraints mattered most?

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?

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
- **Tests and documentation.** The AI wrote the pytest suite, added one-line summary docstrings to every method, and filled in the README with real output from the demo and the tests.

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

**How I verified the results**

- **Ran the code, not just read it.** I ran `python main.py` after every change and checked the schedule by hand: the two 10-minute feedings come first, the completed "Heartworm pill" is missing, the 85 minutes used stay under the 90 available, and the two low-priority weekly tasks are skipped because only 5 minutes are left.
- **Ran the tests.** `pytest` passes all 17 tests, including the two required ones. When the AI changed docstrings, I re-ran the tests to make sure no code had changed by accident.
- **Checked requirements line by line.** For `main.py`, I compared the script against each item in the assignment instead of assuming "it runs" meant "it's done".
- **Asked the AI to prove its claims.** When it said every method had a docstring, it ran a script that listed any function without one (none were missing) instead of me taking its word for it. When it updated the README, I asked it to use only output that actually exists today and leave the unfinished parts (like the Streamlit walkthrough) as placeholders, so the README doesn't describe features I haven't built.
- **Kept the UML in sync.** When `mark_complete()` was added to `Task`, I made sure it was added to `diagrams/uml.mmd` too, so the diagram still matches the code.

The biggest lesson: the AI is fast and usually right, but it will sometimes do more than I asked or make choices I didn't make. Asking "what is this for?" and "does this actually meet the requirement?" kept me in charge of the design.

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
- Why were these tests important?

**b. Confidence**

- How confident are you that your scheduler works correctly?
- What edge cases would you test next if you had more time?

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
