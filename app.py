"""
app.py
PawPal+ — Streamlit UI connected to pawpal_system.py logic layer.

Session state:
    st.session_state.owner  — the single Owner instance for this session
"""

from datetime import date
import streamlit as st
from pawpal_system import Owner, Pet

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")
st.title("🐾 PawPal+")
st.caption("Your personal pet care planning assistant.")
st.divider()

# ---------------------------------------------------------------------------
# Session state — create Owner only once per session
# ---------------------------------------------------------------------------

if "owner" not in st.session_state or (st.session_state.owner is not None and not hasattr(st.session_state.owner, "start_hour")):
    st.session_state.owner = None   # will be set after setup form

owner: Owner | None = st.session_state.owner

# ---------------------------------------------------------------------------
# Section 1 — Owner Setup
# ---------------------------------------------------------------------------

st.subheader("👤 Owner Setup")

if owner is None:
    with st.form("owner_form"):
        owner_name        = st.text_input("Your name", value="Jordan")
        colA, colB = st.columns(2)
        available_minutes = colA.number_input(
            "Daily time budget (minutes)", min_value=10, max_value=480, value=90, step=10
        )
        start_hour = colB.number_input(
            "Day start hour (0-23)", min_value=0, max_value=23, value=8, step=1
        )
        submitted = st.form_submit_button("Start →")

    if submitted:
        st.session_state.owner = Owner(name=owner_name, available_minutes=available_minutes, start_hour=start_hour)
        st.rerun()
    st.stop()   # nothing else renders until owner is created

else:
    col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1])
    col1.markdown(f"**{owner.name}**")
    col2.markdown(f"⏱ {owner.available_minutes} min/day")
    col3.markdown(f"🌅 Starts {owner.start_hour:02d}:00")
    if col4.button("Reset", help="Clear session and start over"):
        del st.session_state.owner
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Pets
# ---------------------------------------------------------------------------

st.subheader("🐾 My Pets")

with st.expander("Add a new pet", expanded=len(owner.get_pets()) == 0):
    with st.form("add_pet_form"):
        col1, col2, col3, col4 = st.columns(4)
        pet_name    = col1.text_input("Name")
        pet_species = col2.selectbox("Species", ["dog", "cat", "rabbit", "bird", "other"])
        pet_breed   = col3.text_input("Breed (optional)")
        pet_age     = col4.number_input("Age", min_value=0, max_value=30, value=1)
        add_pet_btn = st.form_submit_button("Add pet")

    if add_pet_btn:
        if pet_name.strip():
            new_pet = Pet(name=pet_name.strip(), species=pet_species,
                          breed=pet_breed.strip(), age=pet_age)
            owner.add_pet(new_pet)
            st.success(f"Added **{new_pet.name}** the {new_pet.species}!")
            st.rerun()
        else:
            st.warning("Please enter a pet name.")

pets = owner.get_pets()
if not pets:
    st.info("No pets yet. Add one above.")
    st.stop()

for pet in pets:
    task_count = len(pet.get_tasks())
    col1, col2 = st.columns([5, 1])
    col1.markdown(f"**{pet.name}** — {pet.species}"
                  + (f", {pet.breed}" if pet.breed else "")
                  + f" · {pet.age}y · {task_count} task(s)")
    if col2.button("Remove", key=f"remove_pet_{pet.id}"):
        owner.remove_pet(pet.id)
        st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Tasks
# ---------------------------------------------------------------------------

st.subheader("✅ Tasks")

pet_options = {p.name: p for p in pets}
selected_pet_name = st.selectbox("Select pet", list(pet_options.keys()), key="task_pet_select")
selected_pet = pet_options[selected_pet_name]

with st.expander("Add a task", expanded=True):
    with st.form("add_task_form"):
        col1, col2 = st.columns(2)
        task_title = col1.text_input("Task title", value="Morning Walk")
        duration   = col2.number_input("Duration (min)", min_value=1, max_value=240, value=20)

        col3, col4 = st.columns(2)
        priority = col3.selectbox("Priority", ["high", "medium", "low"])
        category = col4.selectbox(
            "Category", ["walk", "feeding", "meds", "grooming", "enrichment", "other"]
        )

        col5, col6 = st.columns(2)
        recurrence = col5.selectbox(
            "Recurrence", ["none", "daily", "weekdays", "weekly"],
            help="How often this task repeats. 'none' = one-time only.",
        )
        preferred_time_slot = col6.selectbox(
            "Preferred slot", ["any", "morning", "afternoon", "evening"],
            help="Soft preference used for conflict detection.",
        )

        notes        = st.text_input("Notes (optional)", value="")
        add_task_btn = st.form_submit_button("Add task")

    if add_task_btn:
        if task_title.strip():
            owner.create_task(
                pet_id=selected_pet.id,
                title=task_title.strip(),
                duration_minutes=int(duration),
                priority=priority,
                category=category,
                notes=notes.strip(),
                recurrence=recurrence,
                preferred_time_slot=preferred_time_slot,
            )
            st.success(f"Added **{task_title}** to {selected_pet.name}.")
            st.rerun()
        else:
            st.warning("Please enter a task title.")

# --- Filter & Sort controls ---
st.markdown("##### Filter & Sort")
fc1, fc2, fc3 = st.columns(3)

filter_status = fc1.selectbox(
    "Filter by status",
    ["all", "pending", "in_progress", "completed"],
    key="filter_status",
)
sort_by = fc2.selectbox(
    "Sort by",
    ["priority", "duration", "category", "title"],
    key="sort_by",
)
show_all_pets = fc3.checkbox(
    "Show all pets", value=False, key="all_pets_tasks",
    help="Display tasks from every pet, not just the selected one.",
)

status_filter = None if filter_status == "all" else filter_status
pet_id_filter = None if show_all_pets else selected_pet.id

tasks = owner.get_filtered_tasks(
    pet_id=pet_id_filter, status=status_filter, sort_by=sort_by
)

# --- Task list ---
if tasks:
    for task in tasks:
        status_icon = {"pending": "⬜", "in_progress": "🔄", "completed": "✅"}.get(task.status, "⬜")
        recur_badge = f" 🔁 `{task.recurrence}`" if task.recurrence != "none" else ""
        slot_badge  = f" 🕐 `{task.preferred_time_slot}`" if task.preferred_time_slot != "any" else ""

        # Show pet name when cross-pet view is active
        pet_label = ""
        if show_all_pets:
            t_pet = next((p for p in pets if p.id == task.pet_id), None)
            pet_label = f" · 🐾 {t_pet.name}" if t_pet else ""

        col1, col2, col3 = st.columns([5, 2, 1])
        col1.markdown(
            f"{status_icon} **{task.title}**{pet_label} — {task.duration_minutes} min "
            f"[{task.priority}, {task.category}]{recur_badge}{slot_badge}"
        )
        new_status = col2.selectbox(
            "Status", ["pending", "in_progress", "completed"],
            index=["pending", "in_progress", "completed"].index(task.status),
            key=f"status_{task.id}",
            label_visibility="collapsed",
        )
        if new_status != task.status:
            if new_status == "completed":
                owner.complete_task(task.id, on_date=str(date.today()))
            else:
                task.set_status(new_status)
            st.rerun()
        if col3.button("🗑", key=f"remove_task_{task.id}"):
            owner.remove_task(task.id)
            st.rerun()
else:
    st.info("No tasks match the current filter.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4 — Schedule
# ---------------------------------------------------------------------------

st.subheader("📅 Today's Schedule")

sched_pet_name = st.selectbox("Schedule for", list(pet_options.keys()), key="sched_pet_select")
sched_pet = pet_options[sched_pet_name]

if st.button("Generate schedule 🗓", type="primary"):
    if not sched_pet.get_tasks():
        st.warning(f"{sched_pet.name} has no tasks to schedule.")
    else:
        schedule = owner.build_schedule(sched_pet.id, str(date.today()))

        # --- Budget summary ---
        utilization = schedule.total_duration_minutes / owner.available_minutes
        st.success(
            f"Schedule built for **{sched_pet.name}** — "
            f"{schedule.total_duration_minutes} min used of {owner.available_minutes} min "
            f"({utilization:.0%})"
        )

        # --- Utilisation hints ---
        if utilization < 0.5:
            st.info("💡 You have time to spare — consider adding enrichment tasks!")
        elif utilization > 0.9:
            st.warning("⚠️ Schedule is nearly full. Low-priority tasks may be bumped tomorrow.")

        # --- Conflict warnings ---
        if schedule.conflicts:
            st.markdown("#### ⚠️ Conflicts Detected")
            for msg in schedule.conflicts:
                st.warning(msg)

        # --- Scheduled tasks with time slots ---
        if schedule.slots:
            st.markdown("#### ✅ Scheduled")
            for slot in schedule.slots:
                recur_badge = (f" 🔁 `{slot.task.recurrence}`"
                               if slot.task.recurrence != "none" else "")
                pref_badge  = (f" 🕐 `{slot.task.preferred_time_slot}`"
                               if slot.task.preferred_time_slot != "any" else "")
                st.markdown(
                    f"- `{slot.time_label(schedule.start_hour)}` **{slot.task.title}** — "
                    f"{slot.task.duration_minutes} min "
                    f"[{slot.task.priority} · {slot.task.category}]{recur_badge}{pref_badge}"
                )

        # --- Unscheduled (skipped) tasks ---
        if schedule.unscheduled_tasks:
            st.markdown("#### ⏭ Skipped (didn't fit in time budget)")
            for task in schedule.unscheduled_tasks:
                st.markdown(
                    f"- **{task.title}** — {task.duration_minutes} min [{task.priority} priority]"
                )

        with st.expander("Full explanation"):
            st.text(schedule.explain())
