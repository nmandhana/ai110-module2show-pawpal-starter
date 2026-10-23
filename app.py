from datetime import date

import streamlit as st

from pawpal_system import FREQUENCIES, PRIORITY_ORDER, Owner, Pet, Scheduler, Task

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Plan your pets' care for the day. Add your pets and their care tasks, tell PawPal+
how much time you have, and it builds a schedule that puts the most important
tasks first — and explains why each task made the cut (or didn't).
"""
)

with st.expander("How the schedule is built", expanded=False):
    st.markdown(
        """
1. Only tasks that are **due today** (or overdue) and not yet complete are considered.
2. They're ranked: **priority** first (high → medium → low), then **daily before
   weekly**, then **shorter tasks first** so more of them fit.
3. Going down that list, each task is kept if it fits in the time left; otherwise
   it's skipped, with the reason shown.
4. Tasks with a **fixed time** (📌) are booked at that time. If two fixed tasks
   overlap, the higher-ranked one keeps the slot and the other is skipped as a conflict.
5. Flexible tasks fill the **earliest free gaps from 08:00**, around the fixed ones,
   so nothing overlaps. If one finds no gap, its minutes are given back and tasks
   that didn't fit earlier get one more try.
6. Marking a task complete books its next occurrence: tomorrow for a daily task,
   a week later for a weekly one.
"""
    )

st.divider()

# The Owner lives in st.session_state (the "vault") so it survives Streamlit's
# rerun on every click. Create it only once; afterwards, reuse the same object
# along with all the pets and tasks attached to it.
if "owner" not in st.session_state:
    st.session_state.owner = Owner(name="Jordan", available_minutes=60)
owner = st.session_state.owner

# Actions in "Your Tasks" change data shown higher up the page, so they save a
# message here and call st.rerun(); the message is shown on the next run.
flash = st.session_state.pop("flash", None)


def rerun_with(message: str) -> None:
    """Remember a success message and rerun so the whole page shows the change."""
    st.session_state.flash = message
    st.rerun()


st.subheader("Owner")
col1, col2 = st.columns(2)
with col1:
    owner.name = st.text_input("Owner name", value=owner.name)
with col2:
    owner.available_minutes = int(
        st.number_input(
            "Time available today (minutes)",
            min_value=0,
            max_value=24 * 60,
            value=owner.available_minutes,
        )
    )

st.subheader("Add a Pet")
col1, col2 = st.columns(2)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add pet"):
    name = pet_name.strip()
    if not name:
        st.error("Please enter a pet name.")
    elif any(p.name == name for p in owner.pets):
        st.error(f"{name} is already in your list.")
    else:
        owner.add_pet(Pet(name=name, species=species))
        st.success(f"Added {name} ({species}).")

if owner.pets:
    st.write("Your pets: " + ", ".join(f"{p.name} ({p.species})" for p in owner.pets))
    with st.expander("Remove a pet"):
        pet_to_remove = st.selectbox("Pet to remove", [p.name for p in owner.pets])
        if st.button("Remove pet"):
            owner.remove_pet(next(p for p in owner.pets if p.name == pet_to_remove))
            rerun_with(f"Removed {pet_to_remove} and all of its tasks.")
else:
    st.info("No pets yet. Add one above.")

st.subheader("Add a Task")
if not owner.pets:
    st.caption("Add a pet first — every task belongs to a pet.")
else:
    pet_choice = st.selectbox("For which pet?", [p.name for p in owner.pets])
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", list(PRIORITY_ORDER), index=0)
    with col4:
        frequency = st.selectbox("Frequency", FREQUENCIES)
    fixed_time = st.text_input(
        "Fixed time (HH:MM, optional)",
        value="",
        placeholder="e.g. 09:00 — leave blank for a flexible task",
    )

    if st.button("Add task"):
        pet = next(p for p in owner.pets if p.name == pet_choice)
        if not task_title.strip():
            st.error("Please enter a task title.")
        else:
            try:
                # Task validates itself; Pet.add_task rejects duplicates and
                # stamps the task with the pet's name.
                pet.add_task(
                    Task(
                        task_title.strip(),
                        int(duration),
                        priority,
                        frequency,
                        time=fixed_time.strip() or None,
                    )
                )
                st.success(f"Added '{task_title.strip()}' for {pet.name}.")
            except ValueError as err:
                st.error(str(err))

if flash:
    st.success(flash)

scheduler = Scheduler()
all_tasks = owner.get_all_tasks()
STATUS_FILTERS = {"All": None, "To do": False, "Done": True}

if all_tasks:
    st.subheader("Your Tasks")
    col1, col2 = st.columns(2)
    with col1:
        pet_filter = st.selectbox("Show pet", ["All pets"] + [p.name for p in owner.pets])
    with col2:
        status_filter = st.selectbox("Show status", list(STATUS_FILTERS))
    shown = owner.filter_tasks(
        completed=STATUS_FILTERS[status_filter],
        pet_name=None if pet_filter == "All pets" else pet_filter,
    )

    if not shown:
        st.info("No tasks match these filters.")
    else:
        st.table(
            [
                {
                    "pet": t.pet_name,
                    "title": t.title,
                    "time": f"📌 {t.time}" if t.time else "flexible",
                    "duration_minutes": t.duration_minutes,
                    "priority": t.priority,
                    "frequency": t.frequency,
                    "due": t.due_date.isoformat(),
                    "done": "✓" if t.completed else "",
                }
                # Timed tasks first in clock order, then flexible ones as added.
                for t in scheduler.sort_by_time(shown)
            ]
        )
        st.caption(f"Showing {len(shown)} of {len(all_tasks)} tasks.")

        # Only the tasks shown can be chosen. Tasks are identified by id() —
        # the objects live in session_state, so the id stays the same across
        # reruns, even if two tasks look alike.
        by_id = {id(t): t for t in shown}
        selected_id = st.selectbox(
            "Choose a task to update",
            list(by_id),
            format_func=lambda i: (
                f"{by_id[i].pet_name} — {by_id[i].title} (due {by_id[i].due_date.isoformat()})"
                + (" ✓" if by_id[i].completed else "")
            ),
        )
        selected = by_id[selected_id]
        selected_pet = next(p for p in owner.pets if p.name == selected.pet_name)

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Mark complete", disabled=selected.completed):
                upcoming = selected_pet.complete_task(selected)
                rerun_with(
                    f"Completed '{selected.title}'. Next one is due "
                    f"{upcoming.due_date.isoformat()}."
                )
        with col2:
            if st.button("Delete task"):
                selected_pet.remove_task(selected)
                rerun_with(f"Deleted '{selected.title}' for {selected_pet.name}.")

        with st.expander("Edit this task"):
            # Keys include the task's id so the form refills when a different
            # task is chosen.
            with st.form(f"edit_{selected_id}"):
                new_title = st.text_input("Title", value=selected.title, key=f"t_{selected_id}")
                new_duration = st.number_input(
                    "Duration",
                    min_value=1,
                    max_value=240,
                    value=selected.duration_minutes,
                    key=f"d_{selected_id}",
                )
                new_priority = st.selectbox(
                    "New priority",
                    list(PRIORITY_ORDER),
                    index=list(PRIORITY_ORDER).index(selected.priority),
                    key=f"p_{selected_id}",
                )
                new_frequency = st.selectbox(
                    "New frequency",
                    FREQUENCIES,
                    index=FREQUENCIES.index(selected.frequency),
                    key=f"f_{selected_id}",
                )
                new_time = st.text_input(
                    "Fixed time (HH:MM, blank = flexible)",
                    value=selected.time or "",
                    key=f"tm_{selected_id}",
                )
                if st.form_submit_button("Save changes"):
                    if not new_title.strip():
                        st.error("Please enter a task title.")
                    else:
                        try:
                            selected_pet.edit_task(
                                selected,
                                title=new_title.strip(),
                                duration_minutes=int(new_duration),
                                priority=new_priority,
                                frequency=new_frequency,
                                time=new_time.strip() or None,
                            )
                            rerun_with(f"Saved changes to '{selected.title}'.")
                        except ValueError as err:
                            st.error(str(err))

st.divider()

st.subheader("Build Schedule")
today = date.today()
st.caption(
    f"Plans tasks due by {today.isoformat()} for all pets within "
    f"{owner.available_minutes} minutes. Flexible tasks start from 08:00."
)

if st.button("Generate schedule"):
    plan = scheduler.build_plan(owner, today)

    if not plan.entries and not plan.skipped:
        st.info("No tasks to schedule. Add some tasks above.")
    else:
        if plan.entries:
            st.markdown("#### Today's Schedule")
            st.table(
                [
                    {
                        "start": e.start_time,
                        "end": e.end_time,
                        "task": ("📌 " if e.task.time else "") + e.task.title,
                        "pet": e.task.pet_name,
                        "minutes": e.task.duration_minutes,
                        "priority": e.task.priority,
                        "why": e.reason,
                    }
                    for e in plan.entries
                ]
            )
        else:
            st.warning("Nothing fits in the time available.")

        if plan.skipped:
            st.markdown("#### Skipped")
            st.table(
                [
                    {"task": s.task.title, "pet": s.task.pet_name, "why": s.reason}
                    for s in plan.skipped
                ]
            )

        with st.expander("Plan explanation (text)"):
            st.text(plan.explain())

        used = sum(e.task.duration_minutes for e in plan.entries)
        st.caption(
            f"{len(plan.entries)} scheduled · {used}/{owner.available_minutes} min used · "
            f"{len(plan.skipped)} skipped"
        )
