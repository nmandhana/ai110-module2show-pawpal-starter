"""PawPal+ logic layer.

Backend classes for the PawPal+ pet care planner, matching diagrams/uml.mmd:

- Data classes: Task, Pet, Owner (dataclasses — they hold information;
  Owner also provides get_all_tasks(), the one method the Scheduler reads)
- Logic: Scheduler (plain stateless class)
- Result: DailyPlan, made of ScheduledTask entries and SkippedTask leftovers

No Streamlit code belongs in this file — the UI (app.py) imports from here,
never the other way around.
"""

import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Optional

# Priority names mapped to sort rank (lower = more important). Strings alone
# sort alphabetically (high < low < medium), which is wrong — the scheduler
# ranks tasks by looking up this mapping instead.
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# How often a task recurs, and how far ahead its next occurrence is due.
# Kept as a validated mapping so typos like "Daily" are caught at
# construction time, same as priorities.
FREQUENCY_DAYS = {"daily": 1, "weekly": 7}
FREQUENCIES = tuple(FREQUENCY_DAYS)

# Flexible tasks are placed from 08:00 (matches the README's sample output),
# in the earliest free gap that doesn't overlap a fixed-time task.
DAY_START_MINUTES = 8 * 60
DAY_END_MINUTES = 24 * 60


def format_time(minutes: int) -> str:
    """Convert minutes-since-midnight to an HH:MM string (480 -> \"08:00\")."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# Strict 24-hour "HH:MM", zero-padded. Requiring the padding means "09:00"
# and "10:00" also sort correctly as plain strings.
_TIME_PATTERN = re.compile(r"([01]\d|2[0-3]):([0-5]\d)")


def parse_time(text: str) -> int:
    """Convert an HH:MM string to minutes-since-midnight ("08:30" -> 510).

    Raises ValueError for anything that isn't a valid zero-padded 24-hour time."""
    match = _TIME_PATTERN.fullmatch(text)
    if not match:
        raise ValueError(f"Invalid time {text!r}; expected 24-hour HH:MM like '08:30'")
    return int(match.group(1)) * 60 + int(match.group(2))


@dataclass
class Task:
    """A single care task. Pure data — no scheduling logic.

    duration_minutes is how long the task takes. time is an optional
    time of day ("HH:MM") for fixed appointments like "meds at 09:00";
    when it's None the task is flexible and the scheduler picks its start
    (ScheduledTask.start_time). pet_name records which pet the task
    belongs to — stamped by Pet.add_task, so a multi-pet plan can say
    whose task is whose. due_date is the day the task is due; recurring
    tasks get a new copy with a later due_date when completed
    (see next_occurrence).
    """

    title: str
    duration_minutes: int
    priority: str  # "low", "medium", or "high"
    frequency: str = "daily"  # "daily" or "weekly"
    completed: bool = False  # flipped when the owner finishes the task
    pet_name: str = ""  # set by Pet.add_task
    time: Optional[str] = None  # fixed time of day "HH:MM", or None if flexible
    due_date: date = field(default_factory=date.today)

    def __post_init__(self):
        """Reject a non-positive duration, an unknown priority or frequency, or a bad time."""
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
        if self.time is not None:
            parse_time(self.time)  # raises ValueError if malformed

    def mark_complete(self, completed_on: Optional[date] = None) -> "Task":
        """Mark this task as done and return its next occurrence.

        The done task drops out of the plan; the returned copy is due a day
        (daily) or a week (weekly) after completed_on (default: today). A
        Task doesn't know which pet's list it's on, so Pet.complete_task()
        is what adds the copy there."""
        self.completed = True
        return self.next_occurrence(completed_on)

    def next_occurrence(self, completed_on: Optional[date] = None) -> "Task":
        """Return a fresh, unfinished copy of this task due one period later.

        Counts from the day it was completed (default: today), so a daily
        task finished today is due today + timedelta(days=1) — even if it
        was overdue, so the next copy isn't overdue too. A task finished
        early (before its due date) counts from its due date instead, so
        finishing tomorrow's walk today books the day after, not tomorrow
        again. timedelta handles month and year ends (Oct 31 -> Nov 1).
        dataclasses.replace() builds a new Task, so validation runs again."""
        start = max(self.due_date, completed_on or date.today())
        return replace(
            self,
            completed=False,
            due_date=start + timedelta(days=FREQUENCY_DAYS[self.frequency]),
        )


@dataclass
class Pet:
    """A pet and the list of care tasks it needs."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task to this pet and stamp it with the pet's name.

        Field validation lives in Task itself (__post_init__); this doorway
        holds the list-level rule: no two unfinished tasks with the same
        title on the same due date. The name stamp lets multi-pet plans
        attribute each task."""
        self._check_duplicate(task)
        task.pet_name = self.name
        self.tasks.append(task)

    def edit_task(self, task: Task, **changes) -> None:
        """Change some of a task's fields in place, e.g. edit_task(t, priority="low").

        The changes are tried on a copy first (dataclasses.replace re-runs
        Task validation), and the duplicate-title rule is checked, so a bad
        edit raises ValueError and leaves the task untouched."""
        self._require_own(task)
        updated = replace(task, **changes)
        self._check_duplicate(updated, ignore=task)
        for name in changes:
            setattr(task, name, getattr(updated, name))

    def remove_task(self, task: Task) -> None:
        """Remove a task from this pet. Raises ValueError if it isn't there."""
        self._require_own(task)
        # Compare by identity: two tasks can hold equal values.
        self.tasks = [existing for existing in self.tasks if existing is not task]

    def complete_task(self, task: Task, completed_on: Optional[date] = None) -> Task:
        """Mark a task complete and add its next occurrence; return the new task.

        This is how recurrence works: completing "Walk" today adds
        tomorrow's "Walk" (or next week's, for a weekly task).
        completed_on defaults to today."""
        self._require_own(task)
        upcoming = task.mark_complete(completed_on)
        self.add_task(upcoming)
        return upcoming

    def _require_own(self, task: Task) -> None:
        """Raise ValueError unless this exact task object is in this pet's list."""
        if not any(existing is task for existing in self.tasks):
            raise ValueError(f"{task.title!r} is not one of {self.name}'s tasks")

    def _check_duplicate(self, task: Task, ignore: Optional[Task] = None) -> None:
        """Raise ValueError if another unfinished task has the same title and due date."""
        for existing in self.tasks:
            if (
                existing is not ignore
                and not existing.completed
                and existing.title.lower() == task.title.lower()
                and existing.due_date == task.due_date
            ):
                raise ValueError(f"{self.name} already has an unfinished task {task.title!r}")


@dataclass
class Owner:
    """The pet owner: their time constraint and the pets they manage."""

    name: str
    available_minutes: int
    pets: list[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner's care."""
        self.pets.append(pet)

    def remove_pet(self, pet: Pet) -> None:
        """Remove a pet (and with it, all of its tasks) from this owner's care."""
        self.pets.remove(pet)

    def get_all_tasks(self) -> list[Task]:
        """Return every pet's tasks together, in pet order.

        This is the single method the Scheduler reads from — only Owner
        knows how pets are stored, so if that storage ever changes, the
        Scheduler doesn't."""
        all_tasks: list[Task] = []
        for pet in self.pets:
            all_tasks.extend(pet.tasks)
        return all_tasks

    def filter_tasks(
        self, completed: Optional[bool] = None, pet_name: Optional[str] = None
    ) -> list[Task]:
        """Return tasks matching the given filters, in pet order.

        Each filter is optional and they combine: completed=False gives
        unfinished tasks, pet_name="Mochi" gives Mochi's tasks, and both
        together give Mochi's unfinished tasks. A filter left as None
        matches everything. Built on get_all_tasks(), so it sees the same
        tasks the Scheduler does."""
        return [
            t
            for t in self.get_all_tasks()
            if (completed is None or t.completed == completed)
            and (pet_name is None or t.pet_name == pet_name)
        ]


@dataclass
class ScheduledTask:
    """One entry in the daily plan: a task, when it starts, and why it was chosen."""

    task: Task
    start_time: str
    reason: str

    @property
    def end_time(self) -> str:
        """The HH:MM time this entry finishes (start + duration)."""
        return format_time(parse_time(self.start_time) + self.task.duration_minutes)


@dataclass
class SkippedTask:
    """A task that didn't make the plan, and why (e.g. not enough time left)."""

    task: Task
    reason: str


@dataclass
class DailyPlan:
    """The result of scheduling: entries in start-time order, the tasks that
    didn't fit, and warnings about fixed-time tasks that overlap."""

    entries: list[ScheduledTask] = field(default_factory=list)
    skipped: list[SkippedTask] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def explain(self) -> str:
        """Return the plan as readable text: conflict warnings first, then one
        line per scheduled or skipped task.

        Built from the reasons the Scheduler recorded at decision time,
        including why each skipped task was left out."""
        if not self.entries and not self.skipped:
            return "No tasks to schedule."
        lines = [f"Warning: {w}" for w in self.warnings]
        for entry in self.entries:
            t = entry.task
            lines.append(
                f"{entry.start_time}–{entry.end_time} — {t.title} ({t.duration_minutes} min, "
                f"{t.pet_name}) [priority: {t.priority}] — {entry.reason}"
            )
        for skip in self.skipped:
            t = skip.task
            lines.append(f"Skipped: {t.title} ({t.pet_name}) — {skip.reason}")
        return "\n".join(lines)


class Scheduler:
    """Decides which tasks fit the owner's time budget, when, and in what order.

    Reads tasks across ALL pets via owner.get_all_tasks() — never from a
    single pet, and never by reaching into owner.pets directly.

    Stateless: holds no attributes, so the same inputs always produce the
    same plan. This keeps it easy to test with pytest, independent of the UI.
    (Not a dataclass on purpose — dataclasses are for classes that carry data,
    and this one carries none.)
    """

    def build_plan(self, owner: Owner, day: Optional[date] = None) -> DailyPlan:
        """Build the plan for `day` (default today) from all pets' unfinished tasks.

        Only tasks due on or before `day` are considered (overdue ones are
        still owed). Three passes, all in rank order:

        1. Choose. Each task that fits the remaining owner.available_minutes
           reserves its minutes. A fixed-time task is booked at its time
           right away unless it overlaps a fixed task already booked —
           ranking first means the more important one keeps the slot.
           Flexible tasks are reserved but not placed yet. Tasks that don't
           fit the budget wait for pass 3.
        2. Place. Reserved flexible tasks go into the earliest free gap from
           08:00 around the appointments, so a flexible task never pushes an
           appointment out. If one finds no gap, its minutes are refunded.
        3. Retry. Tasks that didn't fit the budget get one more chance with
           whatever is left after refunds; any still too long are skipped.

        Every choice — chosen or skipped — records a reason. Entries come
        back sorted by start time, and each entry's reason ends with the
        budget used up to and including it, so the numbers rise down the plan.
        plan.warnings lists every overlap between the day's fixed-time
        tasks (see detect_conflicts), even ones skipped for lack of time."""
        day = day or date.today()
        ranked = self._rank_tasks(
            [t for t in owner.get_all_tasks() if not t.completed and t.due_date <= day]
        )
        plan = DailyPlan(warnings=self.detect_conflicts(ranked, day))
        minutes_left = owner.available_minutes
        booked: list[tuple[int, int, ScheduledTask]] = []  # (start, end, entry)
        reserved: list[Task] = []  # flexible tasks holding budget, not yet placed
        waiting: list[Task] = []  # tasks that didn't fit the budget on first look

        for task in ranked:
            if not self._fits_in_budget(task, minutes_left):
                waiting.append(task)
            elif task.time is None:
                reserved.append(task)
                minutes_left -= task.duration_minutes
            elif self._book_or_skip(task, booked, plan):
                minutes_left -= task.duration_minutes

        for task in reserved:
            if not self._book_or_skip(task, booked, plan):
                minutes_left += task.duration_minutes  # refund: it never ran

        for task in waiting:
            if not self._fits_in_budget(task, minutes_left):
                plan.skipped.append(
                    SkippedTask(
                        task,
                        f"not enough time left (needs {task.duration_minutes} min, "
                        f"only {minutes_left} min remaining)",
                    )
                )
            elif self._book_or_skip(task, booked, plan):
                minutes_left -= task.duration_minutes

        # Reasons are written last, in clock order, so the running total
        # matches the order the owner reads the plan in.
        used = 0
        for _, _, entry in sorted(booked, key=lambda b: b[0]):
            used += entry.task.duration_minutes
            entry.reason = self._reason(entry.task, day, used, owner.available_minutes)
            plan.entries.append(entry)
        # Skipped tasks are listed in rank order, whichever pass skipped them.
        rank = {id(t): i for i, t in enumerate(ranked)}
        plan.skipped.sort(key=lambda s: rank[id(s.task)])
        return plan

    def _book_or_skip(
        self, task: Task, booked: list[tuple[int, int, ScheduledTask]], plan: DailyPlan
    ) -> bool:
        """Try to book the task; if it can't be, add it to plan.skipped with the reason.

        Returns True if it was booked, so the caller knows whether the task
        uses up its minutes."""
        problem = self._try_book(task, booked)
        if problem:
            plan.skipped.append(SkippedTask(task, problem))
            return False
        return True

    def _try_book(self, task: Task, booked: list[tuple[int, int, ScheduledTask]]) -> Optional[str]:
        """Book the task into `booked`; return None on success, or why it can't be booked.

        A fixed-time task must not run past midnight or overlap a booked
        task; a flexible task takes the earliest free gap from 08:00. The
        entry's reason is filled in later by build_plan."""
        if task.time is None:
            start = self._first_free_slot(task.duration_minutes, booked)
            if start is None:
                return "no free slot left today"
        else:
            start = parse_time(task.time)
            if start + task.duration_minutes > DAY_END_MINUTES:
                return "runs past midnight"
            clash = self._find_conflict(start, start + task.duration_minutes, booked)
            if clash is not None:
                return (
                    f"conflicts with {clash.task.title} ({clash.task.pet_name}) "
                    f"at {clash.start_time}–{clash.end_time}"
                )
        end = start + task.duration_minutes
        booked.append((start, end, ScheduledTask(task, format_time(start), "")))
        return None

    def _reason(self, task: Task, day: date, used: int, budget: int) -> str:
        """Build the 'why chosen' text for a scheduled task.

        `used` is the minutes of the budget used by this task and every
        task before it in the plan."""
        timing = f"fixed time {task.time}" if task.time else "earliest free slot"
        reason = f"{task.priority} priority, {task.frequency} task, {timing}"
        if task.due_date < day:
            reason += f" (overdue since {task.due_date.isoformat()})"
        return f"{reason}; {used}/{budget} min used after this"

    def detect_conflicts(self, tasks: list[Task], day: Optional[date] = None) -> list[str]:
        """Return a warning for each pair of fixed-time tasks whose times overlap.

        Checks every pair, whether both tasks belong to the same pet or to
        different pets. Two tasks clash if they fall on the same day and
        their time ranges overlap; touching ends (09:00–09:30, then 09:30)
        don't count. Completed and flexible tasks are ignored — the
        scheduler fits flexible tasks into free gaps, so they can't clash.

        Each task's own due_date is its day, unless `day` is given: then
        only tasks due by `day` are checked, all as if on `day` (that's
        how build_plan treats overdue tasks). Returns warnings rather than
        raising, so callers can show them and carry on; [] means no clashes."""
        timed = self.sort_by_time(
            [
                t
                for t in tasks
                if t.time is not None and not t.completed and (day is None or t.due_date <= day)
            ]
        )
        warnings = []
        for i, a in enumerate(timed):
            a_start = parse_time(a.time)
            a_end = a_start + a.duration_minutes
            for b in timed[i + 1 :]:
                if day is None and a.due_date != b.due_date:
                    continue
                b_start = parse_time(b.time)
                b_end = b_start + b.duration_minutes
                if a_start < b_end and b_start < a_end:
                    who = "same pet" if a.pet_name == b.pet_name else "different pets"
                    clash = "starts at the same time as" if a_start == b_start else "overlaps"
                    warnings.append(
                        f"{a.pet_name}'s {a.title} ({a.time}–{format_time(a_end)}) {clash} "
                        f"{b.pet_name}'s {b.title} ({b.time}–{format_time(b_end)}) "
                        f"on {(day or a.due_date).isoformat()} — {who}"
                    )
        return warnings

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Return tasks in time-of-day order, with flexible (untimed) tasks last.

        The key is a tuple: (t.time is None) is False for timed tasks, and
        False < True, so they come first; t.time then orders them. Plain
        string comparison is correct because Task only accepts zero-padded
        "HH:MM" ("09:00" < "10:00"). sorted() is stable, so flexible tasks
        keep their original order. Returns a new list; the input is unchanged."""
        return sorted(tasks, key=lambda t: (t.time is None, t.time or ""))

    def _rank_tasks(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted by priority, then daily before weekly, then shortest first.

        Daily beats weekly on ties because a daily task skipped today is a
        missed day, while a weekly one has more chances; shorter-first fits
        more tasks into the budget. sorted() is stable, so remaining ties
        keep pet order — plans are deterministic."""
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

    def _find_conflict(
        self, start: int, end: int, booked: list[tuple[int, int, ScheduledTask]]
    ) -> Optional[ScheduledTask]:
        """Return the booked entry that overlaps [start, end), or None.

        Touching ends don't count: 08:00–08:30 and 08:30–09:00 don't overlap."""
        for b_start, b_end, entry in booked:
            if start < b_end and b_start < end:
                return entry
        return None

    def _first_free_slot(
        self, duration: int, booked: list[tuple[int, int, ScheduledTask]]
    ) -> Optional[int]:
        """Return the earliest start from 08:00 where `duration` fits without overlap, or None.

        Walks the booked entries in start-time order with a candidate start.
        If the task fits before the next booking, that's the slot; otherwise
        the candidate jumps to the end of that booking and tries again. Using
        max() means a booking that ends before the candidate (e.g. a 07:30
        walk) never moves it backwards. None if it would run past midnight."""
        candidate = DAY_START_MINUTES
        for b_start, b_end, _ in sorted(booked, key=lambda b: b[0]):
            if candidate + duration <= b_start:
                break
            candidate = max(candidate, b_end)
        if candidate + duration > DAY_END_MINUTES:
            return None
        return candidate
