"""PawPal+ logic layer.

Backend classes for the PawPal+ pet care planner, matching diagrams/uml.mmd:

- Data classes: Task, Pet, Owner (dataclasses — they hold information;
  Owner also provides get_all_tasks(), the one method the Scheduler reads)
- Logic: Scheduler (plain stateless class)
- Result: DailyPlan, made of ScheduledTask entries and SkippedTask leftovers

No Streamlit code belongs in this file — the UI (app.py) imports from here,
never the other way around.
"""

from dataclasses import dataclass, field

# Priority names mapped to sort rank (lower = more important). Strings alone
# sort alphabetically (high < low < medium), which is wrong — the scheduler
# ranks tasks by looking up this mapping instead.
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# How often a task recurs. Kept as a validated set so typos like "Daily"
# are caught at construction time, same as priorities.
FREQUENCIES = ("daily", "weekly")

# The plan's day starts at 08:00 (matches the README's sample output).
# Tasks are scheduled back-to-back from here, so overlaps are impossible.
DAY_START_MINUTES = 8 * 60


def _format_time(minutes: int) -> str:
    """Convert minutes-since-midnight to an HH:MM string (480 -> \"08:00\")."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class Task:
    """A single care task. Pure data — no scheduling logic.

    duration_minutes is how long the task takes (the brief's "time");
    time-of-day is the scheduler's output (ScheduledTask.start_time),
    not a task input. pet_name records which pet the task belongs to —
    stamped by Pet.add_task, so a multi-pet plan can say whose task is whose.
    """

    title: str
    duration_minutes: int
    priority: str  # "low", "medium", or "high"
    frequency: str = "daily"  # "daily" or "weekly"
    completed: bool = False  # flipped when the owner finishes the task
    pet_name: str = ""  # set by Pet.add_task

    def __post_init__(self):
        # Validate here rather than in Pet.add_task so an invalid Task can't
        # even be constructed, no matter where it comes from.
        if self.duration_minutes <= 0:
            raise ValueError(f"Task duration must be positive, got {self.duration_minutes}")
        if self.priority not in PRIORITY_ORDER:
            raise ValueError(
                f"Unknown priority {self.priority!r}; expected one of {list(PRIORITY_ORDER)}"
            )
        if self.frequency not in FREQUENCIES:
            raise ValueError(
                f"Unknown frequency {self.frequency!r}; expected one of {list(FREQUENCIES)}"
            )


@dataclass
class Pet:
    """A pet and the list of care tasks it needs."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task. Field validation lives in Task itself
        (__post_init__); this doorway remains for list-level rules
        (e.g. rejecting duplicate titles later) and stamps the task
        with this pet's name so plans can attribute tasks."""
        task.pet_name = self.name
        self.tasks.append(task)


@dataclass
class Owner:
    """The pet owner: their time constraint and the pets they manage."""

    name: str
    available_minutes: int
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's care."""
        self.pets.append(pet)

    def get_all_tasks(self) -> list[Task]:
        """Return every pet's tasks together, in pet order.

        This is the single method the Scheduler reads from — only Owner
        knows how pets are stored, so if that storage ever changes, the
        Scheduler doesn't."""
        all_tasks: list[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks


@dataclass
class ScheduledTask:
    """One entry in the daily plan: a task, when it starts, and why it was chosen."""

    task: Task
    start_time: str
    reason: str


@dataclass
class SkippedTask:
    """A task that didn't make the plan, and why (e.g. not enough time left)."""

    task: Task
    reason: str


@dataclass
class DailyPlan:
    """The result of scheduling: ordered entries plus the tasks that didn't fit."""

    entries: list[ScheduledTask] = field(default_factory=list)
    skipped: list[SkippedTask] = field(default_factory=list)

    def explain(self) -> str:
        """Return a human-readable explanation of the plan, built from the
        reasons recorded by the Scheduler (plus why skipped tasks were left out)."""
        if not self.entries and not self.skipped:
            return "No tasks to schedule."
        lines = []
        for entry in self.entries:
            t = entry.task
            lines.append(
                f"{entry.start_time} — {t.title} ({t.duration_minutes} min, {t.pet_name}) "
                f"[priority: {t.priority}] — {entry.reason}"
            )
        for skip in self.skipped:
            t = skip.task
            lines.append(f"Skipped: {t.title} ({t.pet_name}) — {skip.reason}")
        return "\n".join(lines)


class Scheduler:
    """Decides which tasks fit the owner's time budget and in what order.

    Reads tasks across ALL pets via owner.get_all_tasks() — never from a
    single pet, and never by reaching into owner.pets directly.

    Stateless: holds no attributes, so the same inputs always produce the
    same plan. This keeps it easy to test with pytest, independent of the UI.
    (Not a dataclass on purpose — dataclasses are for classes that carry data,
    and this one carries none.)
    """

    def build_plan(self, owner: Owner) -> DailyPlan:
        """Get every pet's tasks from owner.get_all_tasks(), skip completed
        ones, rank the rest, keep the ones that fit owner.available_minutes,
        assign back-to-back start times from 08:00, and record a reason for
        every choice — chosen and skipped alike."""
        todo = [t for t in owner.get_all_tasks() if not t.completed]
        plan = DailyPlan()
        minutes_left = owner.available_minutes
        current_time = DAY_START_MINUTES

        for task in self._rank_tasks(todo):
            if self._fits_in_budget(task, minutes_left):
                reason = (
                    f"{task.priority} priority, {task.frequency} task, "
                    f"fits in the {minutes_left} min remaining"
                )
                plan.entries.append(
                    ScheduledTask(task, _format_time(current_time), reason)
                )
                current_time += task.duration_minutes
                minutes_left -= task.duration_minutes
            else:
                plan.skipped.append(
                    SkippedTask(
                        task,
                        f"not enough time left (needs {task.duration_minutes} min, "
                        f"only {minutes_left} min remaining)",
                    )
                )
        return plan

    def _rank_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return tasks in scheduling order: priority first (high before low),
        then daily before weekly on ties (a daily task skipped today is a
        missed day; a weekly one has more chances), then shorter duration
        first (fits more tasks into the budget). sorted() is stable, so
        remaining ties keep pet order — plans are deterministic."""
        return sorted(
            tasks,
            key=lambda t: (
                PRIORITY_ORDER[t.priority],
                FREQUENCIES.index(t.frequency),
                t.duration_minutes,
            ),
        )

    def _fits_in_budget(self, task: Task, minutes_left: int) -> bool:
        """Return True if the task can fit in the remaining time budget."""
        return task.duration_minutes <= minutes_left
