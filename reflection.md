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

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
- How did you evaluate or verify what the AI suggested?

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
