"""PawPal+ logic layer.

Backend classes for the PawPal+ pet care planner, matching diagrams/uml.mmd:

- Data classes: Owner, Pet, Task (dataclasses — they only hold information)
- Logic: Scheduler (plain stateless class)
- Result: DailyPlan, made of ScheduledTask entries

No Streamlit code belongs in this file — the UI (app.py) imports from here,
never the other way around.
"""

from dataclasses import dataclass, field

# Priority names mapped to sort rank (lower = more important). Strings alone
# sort alphabetically (high < low < medium), which is wrong — the scheduler
# ranks tasks by looking up this mapping instead.
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


@dataclass
class Owner:
    """The pet owner and their scheduling constraint (time available today)."""

    name: str
    available_minutes: int


@dataclass
class Task:
    """A single care task. Pure data — no scheduling logic."""

    title: str
    duration_minutes: int
    priority: str  # "low", "medium", or "high"


@dataclass
class Pet:
    """A pet and the list of care tasks it needs."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task. All task additions go through this single doorway
        so validation lives in one place."""
        if task.duration_minutes <= 0:
            raise ValueError(f"Task duration must be positive, got {task.duration_minutes}")
        if task.priority not in PRIORITY_ORDER:
            raise ValueError(
                f"Unknown priority {task.priority!r}; expected one of {list(PRIORITY_ORDER)}"
            )
        self.tasks.append(task)


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
        # TODO: implement
        raise NotImplementedError


class Scheduler:
    """Decides which tasks fit the owner's time budget and in what order.

    Stateless: holds no attributes, so the same inputs always produce the
    same plan. This keeps it easy to test with pytest, independent of the UI.
    (Not a dataclass on purpose — dataclasses are for classes that carry data,
    and this one carries none.)
    """

    def build_plan(self, owner: Owner, pet: Pet) -> DailyPlan:
        """Rank the pet's tasks, keep the ones that fit owner.available_minutes,
        assign start times, and record a reason for every choice."""
        # TODO: implement
        raise NotImplementedError

    def _rank_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return tasks ordered by priority (high first)."""
        # TODO: implement
        raise NotImplementedError

    def _fits_in_budget(self, task: Task, minutes_left: int) -> bool:
        """Return True if the task can fit in the remaining time budget."""
        # TODO: implement
        raise NotImplementedError
