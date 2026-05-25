# your_app/management/commands/seed_scheduler.py

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from api.models import (
    Business, Employee, EmployeeStatus,
    Skill, EmployeeSkill, Shift
)
from datetime import date, timedelta, time

User = get_user_model()

# ── Configuration ──────────────────────────────────────────
SHIFTS_PER_DAY = [
    {"name": "Morning",   "start": time(6, 0),  "end": time(12, 0)},
    {"name": "Afternoon", "start": time(12, 0), "end": time(16, 0)},
    {"name": "Evening",   "start": time(16, 0), "end": time(22, 0)},
]

SKILLS = [
    {"name": "Basic Cashiering",    "description": "Basic POS register operations"},
    {"name": "Senior Cashiering",   "description": "Voids, refunds, and senior register ops"},
    {"name": "Store Supervision",   "description": "Floor management and staff supervision"},
    {"name": "Inventory Management","description": "Stock checking and inventory updates"},
]

# Which shifts require which skill
SHIFT_SKILL_MAP = {
    "Morning":   "Basic Cashiering",
    "Afternoon": "Senior Cashiering",
    "Evening":   "Senior Cashiering",
}

# Days ahead to create shifts for
DAYS_AHEAD = 7

class Command(BaseCommand):
    help = "Seed skills, employee skills, and shifts for WSM scheduler testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--business_id",
            type=int,
            default=1,
            help="Business ID to seed data for (default: 1)",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days ahead to create shifts (default: 7)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing unscheduled shifts before seeding",
        )

    def handle(self, *args, **options):
        business_id = options["business_id"]
        days_ahead  = options["days"]
        clear       = options["clear"]

        # ── Get Business ───────────────────────────────────
        try:
            business = Business.objects.get(id=business_id)
            self.stdout.write(f"Business: {business.business_name}")
        except Business.DoesNotExist:
            self.stderr.write(f"Business ID {business_id} not found.")
            self.stderr.write("Available businesses:")
            for b in Business.objects.all():
                self.stderr.write(f"  ID {b.id}: {b.business_name}")
            return

        # ── Step 1: Create Skills ──────────────────────────
        self.stdout.write("\n── Step 1: Creating skills...")
        skill_objects = {}
        for skill_data in SKILLS:
            skill, created = Skill.objects.get_or_create(
                name=skill_data["name"],
                business_id=business,
                defaults={"description": skill_data["description"]},
            )
            skill_objects[skill.name] = skill
            status = "created" if created else "exists"
            self.stdout.write(f"   {skill.name} [{status}]")

        # ── Step 2: Assign Skills to Employees ─────────────
        self.stdout.write("\n── Step 2: Assigning skills to employees...")
        employees = Employee.objects.filter(business_id=business)

        if not employees.exists():
            self.stderr.write("   No employees found for this business.")
            self.stderr.write("   Add employees first via the frontend or admin panel.")
            return

        self.stdout.write(f"   Found {employees.count()} employees")

        for i, employee in enumerate(employees):
            position = (employee.position or "").lower()

            # Assign skills based on position
            if any(w in position for w in ["manager", "supervisor"]):
                skills_to_assign = [
                    ("Basic Cashiering",     "Advanced"),
                    ("Senior Cashiering",    "Advanced"),
                    ("Store Supervision",    "Advanced"),
                    ("Inventory Management", "Intermediate"),
                ]
            elif any(w in position for w in ["senior", "lead"]):
                skills_to_assign = [
                    ("Basic Cashiering",  "Advanced"),
                    ("Senior Cashiering", "Advanced"),
                ]
            elif any(w in position for w in ["cashier", "sales", "associate"]):
                skills_to_assign = [
                    ("Basic Cashiering", "Intermediate"),
                ]
            elif any(w in position for w in ["inventory", "stock"]):
                skills_to_assign = [
                    ("Basic Cashiering",     "Beginner"),
                    ("Inventory Management", "Advanced"),
                ]
            else:
                # Default — give everyone basic cashiering
                skills_to_assign = [
                    ("Basic Cashiering", "Beginner"),
                ]

            for skill_name, proficiency in skills_to_assign:
                if skill_name in skill_objects:
                    emp_skill, created = EmployeeSkill.objects.get_or_create(
                        employee=employee,
                        skill=skill_objects[skill_name],
                        defaults={"proficiency_level": proficiency},
                    )
                    status = "assigned" if created else "exists"
                    self.stdout.write(
                        f"   {employee.name} → {skill_name} "
                        f"({proficiency}) [{status}]"
                    )

        # ── Step 3: Clear existing shifts if requested ─────
        if clear:
            deleted, _ = Shift.objects.filter(
                business_id=business,
                is_scheduled=False,
            ).delete()
            self.stdout.write(f"\n── Cleared {deleted} unscheduled shifts")

        # ── Step 4: Create Shifts ──────────────────────────
        self.stdout.write(f"\n── Step 3: Creating shifts for next {days_ahead} days...")
        shifts_created = 0
        shifts_existed = 0

        for day_offset in range(days_ahead):
            shift_date = date.today() + timedelta(days=day_offset)
            day_name   = shift_date.strftime("%A")

            for shift_config in SHIFTS_PER_DAY:
                required_skill_name = SHIFT_SKILL_MAP.get(shift_config["name"])
                required_skill      = skill_objects.get(required_skill_name)

                shift, created = Shift.objects.get_or_create(
                    business_id  = business,
                    shift_date   = shift_date,
                    start_time   = shift_config["start"],
                    end_time     = shift_config["end"],
                    defaults={
                        "required_skill":     required_skill,
                        "required_employees": 1,
                        "is_scheduled":       False,
                    },
                )

                if created:
                    shifts_created += 1
                    self.stdout.write(
                        f"   {day_name} {shift_date} "
                        f"{shift_config['name']} "
                        f"({shift_config['start']}–{shift_config['end']}) "
                        f"→ {required_skill_name}"
                    )
                else:
                    shifts_existed += 1

        # ── Summary ────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write("SEED COMPLETE")
        self.stdout.write("─" * 50)
        self.stdout.write(f"Skills:         {len(skill_objects)}")
        self.stdout.write(f"Employees:      {employees.count()}")
        self.stdout.write(f"Shifts created: {shifts_created}")
        self.stdout.write(f"Shifts existed: {shifts_existed}")
        self.stdout.write(f"Total shifts:   {shifts_created + shifts_existed}")
        self.stdout.write("\nRun the scheduler:")
        self.stdout.write(
            f"  POST /api/scheduler/schedule/ "
            f"with business_id={business_id}"
        )