"""UI tests for the PawPal+ Streamlit app (app.py).

Uses Streamlit's AppTest to run the app headlessly, fill in widgets and
click buttons, then check what the page shows.

Run from the project root with:  pytest
"""

from datetime import date, timedelta

import pytest
from streamlit.testing.v1 import AppTest

# The first run imports Streamlit and pawpal_system, which can take a few
# seconds — longer than AppTest's 3-second default.
TIMEOUT = 30


@pytest.fixture
def app():
    """A freshly loaded app with an empty owner."""
    at = AppTest.from_file("app.py", default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    return at


def widget(elements, label):
    """Return the widget in `elements` with the given label."""
    return next(e for e in elements if e.label == label)


def add_pet(at, name, species="dog"):
    """Fill in the pet form and click Add pet."""
    widget(at.text_input, "Pet name").set_value(name)
    widget(at.selectbox, "Species").set_value(species)
    widget(at.button, "Add pet").click().run()


def add_task(at, pet, title, minutes, priority="high", frequency="daily", time=""):
    """Fill in the task form for `pet` and click Add task."""
    widget(at.selectbox, "For which pet?").set_value(pet)
    widget(at.text_input, "Task title").set_value(title)
    widget(at.number_input, "Duration (minutes)").set_value(minutes)
    widget(at.selectbox, "Priority").set_value(priority)
    widget(at.selectbox, "Frequency").set_value(frequency)
    widget(at.text_input, "Fixed time (HH:MM, optional)").set_value(time)
    widget(at.button, "Add task").click().run()


def choose_task(at, title):
    """Pick the task with this title in the "Choose a task to update" dropdown."""
    owner = at.session_state.owner
    task = next(t for t in owner.get_all_tasks() if t.title == title and not t.completed)
    widget(at.selectbox, "Choose a task to update").set_value(id(task)).run()
    return task


def test_app_loads_with_no_pets(app):
    """The page loads without errors and starts with an empty owner."""
    assert app.title[0].value == "🐾 PawPal+"
    assert app.session_state.owner.pets == []
    assert any("No pets yet" in i.value for i in app.info)


def test_add_pet_stores_pet_on_owner(app):
    """Clicking Add pet calls owner.add_pet() and confirms it."""
    add_pet(app, "Biscuit", "dog")

    pets = app.session_state.owner.pets
    assert [(p.name, p.species) for p in pets] == [("Biscuit", "dog")]
    assert "Added Biscuit (dog)." in app.success[0].value


def test_duplicate_pet_is_rejected(app):
    """Adding the same pet name twice shows an error and keeps one pet."""
    add_pet(app, "Biscuit")
    add_pet(app, "Biscuit")

    assert len(app.session_state.owner.pets) == 1
    assert "already in your list" in app.error[0].value


def test_blank_pet_name_is_rejected(app):
    """A blank pet name shows an error and adds nothing."""
    add_pet(app, "   ")

    assert app.session_state.owner.pets == []
    assert "Please enter a pet name." in app.error[0].value


def test_add_task_goes_to_chosen_pet(app):
    """Add task calls pet.add_task() on the pet picked in the dropdown."""
    add_pet(app, "Biscuit", "dog")
    add_pet(app, "Mochi", "cat")
    add_task(app, "Mochi", "Feeding", 10)

    owner = app.session_state.owner
    biscuit, mochi = owner.pets
    assert biscuit.tasks == []
    assert [t.title for t in mochi.tasks] == ["Feeding"]
    assert mochi.tasks[0].pet_name == "Mochi"


def test_blank_task_title_is_rejected(app):
    """A blank task title shows an error and saves nothing."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "  ", 10)

    assert app.session_state.owner.get_all_tasks() == []
    assert "Please enter a task title." in app.error[0].value


def test_state_survives_reruns(app):
    """Pets and tasks persist across reruns because Owner lives in session_state."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)

    app.run()  # simulate another interaction / rerun

    assert [t.title for t in app.session_state.owner.get_all_tasks()] == ["Walk"]


def test_generate_schedule_shows_plan_and_skipped(app):
    """Generate schedule calls Scheduler.build_plan() and shows both tables."""
    widget(app.number_input, "Time available today (minutes)").set_value(40).run()
    add_pet(app, "Biscuit", "dog")
    add_pet(app, "Mochi", "cat")
    add_task(app, "Biscuit", "Walk", 30, "high")
    add_task(app, "Mochi", "Feeding", 10, "high")
    add_task(app, "Mochi", "Grooming", 45, "low")

    widget(app.button, "Generate schedule").click().run()
    assert not app.exception

    # Tables on the page: [0] current tasks, [1] schedule, [2] skipped.
    schedule = app.table[1].value
    skipped = app.table[2].value
    assert list(schedule["task"]) == ["Feeding", "Walk"]
    assert list(schedule["start"]) == ["08:00", "08:10"]
    assert list(skipped["task"]) == ["Grooming"]
    assert "not enough time" in skipped["why"].iloc[0]
    assert "2 scheduled · 40/40 min used · 1 skipped" in app.caption[-1].value


def test_generate_with_no_tasks_shows_message(app):
    """Generating with no tasks shows a friendly message, not a crash."""
    widget(app.button, "Generate schedule").click().run()

    assert not app.exception
    assert any("No tasks to schedule" in i.value for i in app.info)


def test_fixed_time_task_is_scheduled_at_its_time(app):
    """A time entered in the form is stored and the schedule books it then."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Meds", 5, time="09:30")
    add_task(app, "Biscuit", "Walk", 30)

    assert app.session_state.owner.get_all_tasks()[0].time == "09:30"

    widget(app.button, "Generate schedule").click().run()
    schedule = app.table[1].value
    assert list(schedule["task"]) == ["Walk", "📌 Meds"]
    assert list(schedule["start"]) == ["08:00", "09:30"]


def test_bad_time_shows_error(app):
    """An invalid time is rejected with Task's own error message."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Meds", 5, time="9am")

    assert app.session_state.owner.get_all_tasks() == []
    assert "Invalid time" in app.error[0].value


def test_duplicate_task_shows_error(app):
    """Adding the same unfinished task twice for a pet is refused."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)
    add_task(app, "Biscuit", "Walk", 30)

    assert len(app.session_state.owner.get_all_tasks()) == 1
    assert "already has an unfinished task" in app.error[0].value


def test_mark_complete_books_next_occurrence(app):
    """Mark complete finishes the task and adds tomorrow's copy."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)
    choose_task(app, "Walk")

    widget(app.button, "Mark complete").click().run()

    done, upcoming = app.session_state.owner.get_all_tasks()
    assert done.completed and not upcoming.completed
    assert upcoming.due_date == date.today() + timedelta(days=1)
    assert "Next one is due" in app.success[0].value

    # Neither copy is in today's plan: one is done, the other is due tomorrow.
    widget(app.button, "Generate schedule").click().run()
    assert any("No tasks to schedule" in i.value for i in app.info)


def test_delete_task(app):
    """Delete task removes only the chosen task."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)
    add_task(app, "Biscuit", "Feeding", 10)
    choose_task(app, "Walk")

    widget(app.button, "Delete task").click().run()

    assert [t.title for t in app.session_state.owner.get_all_tasks()] == ["Feeding"]


def test_edit_task_saves_changes(app):
    """The edit form updates the chosen task in place."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)
    task = choose_task(app, "Walk")

    widget(app.number_input, "Duration").set_value(45)
    widget(app.selectbox, "New priority").set_value("low")
    widget(app.text_input, "Fixed time (HH:MM, blank = flexible)").set_value("07:15")
    widget(app.button, "Save changes").click().run()

    assert not app.exception
    assert (task.duration_minutes, task.priority, task.time) == (45, "low", "07:15")
    assert "Saved changes" in app.success[0].value


def test_remove_pet(app):
    """Remove pet drops the pet and its tasks."""
    add_pet(app, "Biscuit")
    add_pet(app, "Mochi", "cat")
    add_task(app, "Mochi", "Feeding", 10)

    widget(app.selectbox, "Pet to remove").set_value("Mochi")
    widget(app.button, "Remove pet").click().run()

    owner = app.session_state.owner
    assert [p.name for p in owner.pets] == ["Biscuit"]
    assert owner.get_all_tasks() == []


def test_plan_explanation_is_shown(app):
    """The schedule includes DailyPlan.explain() text."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)

    widget(app.button, "Generate schedule").click().run()

    assert "08:00–08:30 — Walk" in app.text[0].value


def test_task_filters_limit_table_and_dropdown(app):
    """The pet and status filters narrow both the table and the task dropdown."""
    add_pet(app, "Biscuit")
    add_pet(app, "Mochi", "cat")
    add_task(app, "Biscuit", "Walk", 30)
    add_task(app, "Mochi", "Feeding", 10)
    add_task(app, "Mochi", "Brush", 10, "low")
    choose_task(app, "Brush")
    widget(app.button, "Mark complete").click().run()

    widget(app.selectbox, "Show pet").set_value("Mochi")
    widget(app.selectbox, "Show status").set_value("To do").run()

    # Mochi's unfinished tasks: Feeding, and tomorrow's Brush.
    assert list(app.table[0].value["title"]) == ["Feeding", "Brush"]
    assert list(app.table[0].value["done"]) == ["", ""]
    assert len(widget(app.selectbox, "Choose a task to update").options) == 2
    assert "Showing 2 of 4 tasks." in [c.value for c in app.caption]

    widget(app.selectbox, "Show status").set_value("Done").run()
    assert list(app.table[0].value["title"]) == ["Brush"]
    assert list(app.table[0].value["done"]) == ["✓"]


def test_filters_with_no_matches_show_message(app):
    """Filters that match nothing show a message instead of an empty table."""
    add_pet(app, "Biscuit")
    add_task(app, "Biscuit", "Walk", 30)

    widget(app.selectbox, "Show status").set_value("Done").run()

    assert not app.exception
    assert any("No tasks match these filters." in i.value for i in app.info)
    assert not any(s.label == "Choose a task to update" for s in app.selectbox)
