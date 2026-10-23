"""Temporary testing ground: build a sample owner with two pets, show the
tasks sorted by time and filtered by pet/status, then run the Scheduler and
print the plan to the terminal.

Run with:  python main.py
"""

from pawpal_system import DailyPlan, Owner, Pet, Scheduler, Task

WIDTH = 62


def print_tasks(heading: str, tasks: list[Task]) -> None:
    """Print a list of tasks as an aligned table: time, title, pet, due date, status."""
    print(f"  {heading}")
    print("  " + "-" * (WIDTH - 2))
    if not tasks:
        print("  (none)")
    title_w = max([len("TASK")] + [len(t.title) for t in tasks]) + 2
    pet_w = max([len("PET")] + [len(t.pet_name) for t in tasks]) + 2
    for t in tasks:
        time = t.time or "flexible"
        status = "done" if t.completed else "to do"
        print(
            f"  {time:<10}{t.title:<{title_w}}{t.pet_name:<{pet_w}}"
            f"due {t.due_date.isoformat()}  {status}"
        )
    print()


def print_schedule(owner: Owner, plan: DailyPlan) -> None:
    """Print the plan as an aligned table: scheduled tasks, skipped tasks, summary.

    Formatting lives here, not in pawpal_system.py, so the backend stays
    free of presentation code. Fixed-time tasks are marked with a 📌; the
    full per-task reasons from DailyPlan.explain() are printed at the end.
    """
    all_tasks = [e.task for e in plan.entries] + [s.task for s in plan.skipped]
    # Size the TASK and PET columns to the longest value so rows never misalign.
    title_w = max([len("TASK")] + [len(t.title) for t in all_tasks]) + 2
    pet_w = max([len("PET")] + [len(t.pet_name) for t in all_tasks]) + 2
    rule = "  " + "-" * (WIDTH - 2)

    pets = ", ".join(f"{p.name} ({p.species})" for p in owner.pets)
    print("=" * WIDTH)
    print("  🐾 TODAY'S SCHEDULE")
    print(f"  Owner: {owner.name}   Pets: {pets}")
    print(f"  Time available: {owner.available_minutes} min")
    print("=" * WIDTH)

    if plan.entries:
        print(f"  {'TIME':<14}{'TASK':<{title_w}}{'PET':<{pet_w}}{'MIN':>4}  PRIORITY")
        print(rule)
        for entry in plan.entries:
            t = entry.task
            slot = f"{entry.start_time}–{entry.end_time}"
            pin = " 📌" if t.time else ""
            print(
                f"  {slot:<14}{t.title:<{title_w}}{t.pet_name:<{pet_w}}"
                f"{t.duration_minutes:>4}  {t.priority.upper()}{pin}"
            )
    else:
        print("  No tasks scheduled.")

    if plan.skipped:
        print()
        print("  SKIPPED")
        print(rule)
        for skip in plan.skipped:
            t = skip.task
            print(f"  ✗ {t.title:<{title_w}}{t.pet_name:<{pet_w}}{skip.reason}")

    used = sum(e.task.duration_minutes for e in plan.entries)
    print()
    print("  Why: priority (high → low), then daily before weekly, then")
    print("  shortest first; 📌 tasks keep their fixed time, the rest fill")
    print("  the earliest free gaps from 08:00 until the time runs out.")
    print("=" * WIDTH)
    print(
        f"  {len(plan.entries)} tasks scheduled · "
        f"{used}/{owner.available_minutes} min used · "
        f"{owner.available_minutes - used} min free"
    )
    print("=" * WIDTH)
    print()
    print("Details (DailyPlan.explain()):")
    print(plan.explain())


def main() -> None:
    """Build a sample owner with two pets, sort and filter their tasks, and print the plan."""
    # Task.due_date defaults to today, so every task below is due today.
    # The fixed-time tasks are added out of clock order (17:00, 07:30, 18:00,
    # 08:15) on purpose, so sort_by_time() has something to fix.
    owner = Owner(name="Jordan", available_minutes=90)

    biscuit = Pet(name="Biscuit", species="dog")
    biscuit.add_task(Task("Feeding", 10, "high"))
    biscuit.add_task(Task("Grooming", 45, "low", frequency="weekly", time="17:00"))
    biscuit.add_task(Task("Morning walk", 30, "high", time="07:30"))
    heartworm = Task("Heartworm pill", 5, "high", frequency="weekly")
    biscuit.add_task(heartworm)
    # Already given today: completing a recurring task books its next
    # occurrence (here, a week from today), so it's out of today's plan.
    biscuit.complete_task(heartworm)

    mochi = Pet(name="Mochi", species="cat")
    mochi.add_task(Task("Feeding", 10, "high"))
    mochi.add_task(Task("Litter box", 15, "medium"))
    mochi.add_task(Task("Play session", 20, "medium", time="18:00"))
    mochi.add_task(Task("Nail trim", 15, "low", frequency="weekly"))
    mochi.add_task(Task("Vet call", 15, "medium", time="08:15"))  # fixed appointment

    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    scheduler = Scheduler()

    print("=" * WIDTH)
    print("  🐾 TASKS")
    print("=" * WIDTH)
    print_tasks("As added (pet order)", owner.get_all_tasks())
    print_tasks("Sorted by time — sort_by_time()", scheduler.sort_by_time(owner.get_all_tasks()))
    print_tasks('Mochi only — filter_tasks(pet_name="Mochi")', owner.filter_tasks(pet_name="Mochi"))
    print_tasks("Done — filter_tasks(completed=True)", owner.filter_tasks(completed=True))
    print_tasks(
        'Biscuit, to do — filter_tasks(completed=False, pet_name="Biscuit")',
        owner.filter_tasks(completed=False, pet_name="Biscuit"),
    )

    plan = scheduler.build_plan(owner)
    print_schedule(owner, plan)


if __name__ == "__main__":
    main()
