"""Temporary testing ground: build a sample owner with two pets, run the
Scheduler, and print the plan to the terminal.

Run with:  python main.py
"""

from pawpal_system import DailyPlan, Owner, Pet, Scheduler, Task

WIDTH = 62


def end_time(start: str, minutes: int) -> str:
    """Return the HH:MM time `minutes` after an HH:MM start ("08:20", 30 -> "08:50")."""
    hours, mins = map(int, start.split(":"))
    total = hours * 60 + mins + minutes
    return f"{total // 60:02d}:{total % 60:02d}"


def print_schedule(owner: Owner, plan: DailyPlan) -> None:
    """Print the plan as an aligned table: scheduled tasks, skipped tasks, summary.

    Formatting lives here, not in pawpal_system.py, so the backend stays
    free of presentation code. DailyPlan.explain() still gives the full
    per-task reasons when they're needed.
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
            slot = f"{entry.start_time}–{end_time(entry.start_time, t.duration_minutes)}"
            print(
                f"  {slot:<14}{t.title:<{title_w}}{t.pet_name:<{pet_w}}"
                f"{t.duration_minutes:>4}  {t.priority.upper()}"
            )
    else:
        print("  No tasks scheduled.")

    if plan.skipped:
        print()
        print("  SKIPPED (not enough time)")
        print(rule)
        for skip in plan.skipped:
            t = skip.task
            print(f"  ✗ {t.title:<{title_w}}{t.pet_name:<{pet_w}}needs {t.duration_minutes} min")

    used = sum(e.task.duration_minutes for e in plan.entries)
    print()
    print("  Why this order: priority (high → low), then daily before weekly,")
    print("  then shortest first; tasks added until the time ran out.")
    print("=" * WIDTH)
    print(
        f"  {len(plan.entries)} tasks scheduled · "
        f"{used}/{owner.available_minutes} min used · "
        f"{owner.available_minutes - used} min free"
    )
    print("=" * WIDTH)


def main() -> None:
    owner = Owner(name="Jordan", available_minutes=90)

    biscuit = Pet(name="Biscuit", species="dog")
    biscuit.add_task(Task("Morning walk", 30, "high"))
    biscuit.add_task(Task("Feeding", 10, "high"))
    biscuit.add_task(Task("Grooming", 45, "low", frequency="weekly"))
    biscuit.add_task(Task("Heartworm pill", 5, "high", completed=True))

    mochi = Pet(name="Mochi", species="cat")
    mochi.add_task(Task("Feeding", 10, "high"))
    mochi.add_task(Task("Litter box", 15, "medium"))
    mochi.add_task(Task("Play session", 20, "medium"))
    mochi.add_task(Task("Nail trim", 15, "low", frequency="weekly"))

    owner.add_pet(biscuit)
    owner.add_pet(mochi)

    plan = Scheduler().build_plan(owner)
    print_schedule(owner, plan)


if __name__ == "__main__":
    main()
