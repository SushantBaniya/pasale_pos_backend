# your_app/services/scheduler.py

from datetime import date, timedelta
from django.db.models import Q
from api.models import Employee, Shift, EmployeeSkill, EmployeeSchedule

# CONFIGURATION

WEIGHTS = {
    "availability":  0.30,
    "skill_match":   0.25,
    "fairness":      0.20,
    "skill_level":   0.15,
    "cost":          0.10,
}

PROFICIENCY_SCORE = {
    "Beginner":     0.4,
    "Intermediate": 0.7,
    "Advanced":     1.0,
}



def normalize(value, min_val, max_val):
    if max_val == min_val:
        return 1.0
    return (value - min_val) / (max_val - min_val)


def is_available(employee, shift):
    return not EmployeeSchedule.objects.filter(
        employee=employee,
        date=shift.shift_date,
    ).filter(
        Q(start_time__lt=shift.end_time) &
        Q(end_time__gt=shift.start_time)
    ).exists()


def get_shifts_this_week(employee, shift_date, max_hours_per_week=40):
    week_start = shift_date - timedelta(days=shift_date.weekday())
    week_end   = week_start + timedelta(days=6)
    return Shift.objects.filter(
        assigned_employee=employee,
        shift_date__range=(week_start, week_end),
        is_scheduled=True,
    ).count()


def get_skill_match(employee, shift):
    if not shift.required_skill:
        return True, 1.0
    try:
        emp_skill = EmployeeSkill.objects.get(
            employee=employee,
            skill=shift.required_skill
        )
        return True, PROFICIENCY_SCORE.get(emp_skill.proficiency_level, 0.4)
    except EmployeeSkill.DoesNotExist:
        return False, 0.0


class WSMStaffScheduler:
    def __init__(self, business_id, shifts, weights=None, max_hours_per_week=40):
        self.business_id       = business_id
        self.shifts            = shifts.order_by('shift_date', 'start_time')
        self.max_hours         = max_hours_per_week
        self.weights           = weights or WEIGHTS
        self.schedule          = []   # list of (shift, employee, score)
        self.unscheduled       = []   # list of shifts with no eligible employee
        
        # 1. Pre-fetch Active Employees
        self.all_employees = list(Employee.objects.filter(
            business_id=business_id,
            status__name="Active"
        ))
        
        if not self.all_employees:
            return

        # 2. Pre-fetch Skills into a lookup dictionary: {(employee_id, skill_id): proficiency_score}
        emp_skills = EmployeeSkill.objects.filter(employee__in=self.all_employees)
        self.skill_lookup = {
            (es.employee_id, es.skill_id): PROFICIENCY_SCORE.get(es.proficiency_level, 0.4)
            for es in emp_skills
        }

        # 3. Pre-fetch Existing Schedules for the date range of the shifts
        if self.shifts.exists():
            start_date = self.shifts.first().shift_date
            end_date   = self.shifts.last().shift_date
            existing_schedules = EmployeeSchedule.objects.filter(
                employee__in=self.all_employees,
                date__range=(start_date, end_date)
            )
            # Lookup: {employee_id: [ (date, start, end), ... ]}
            self.schedule_lookup = {}
            for s in existing_schedules:
                if s.employee_id not in self.schedule_lookup:
                    self.schedule_lookup[s.employee_id] = []
                self.schedule_lookup[s.employee_id].append((s.date, s.start_time, s.end_time))
            
            # 4. Pre-calculate weekly shift counts for fairness
            self.weekly_counts = {e.id: get_shifts_this_week(e, start_date) for e in self.all_employees}
        else:
            self.schedule_lookup = {}
            self.weekly_counts = {e.id: 0 for e in self.all_employees}

    def _is_available_fast(self, employee, shift):
        # Check pre-fetched schedules
        schedules = self.schedule_lookup.get(employee.id, [])
        for (date, start, end) in schedules:
            if date == shift.shift_date:
                if start < shift.end_time and end > shift.start_time:
                    return False
        # Also check shifts we JUST scheduled in this run
        for entry in self.schedule:
            if entry["employee"].id == employee.id and entry["shift"].shift_date == shift.shift_date:
                s = entry["shift"]
                if s.start_time < shift.end_time and s.end_time > shift.start_time:
                    return False
        return True

    def _get_skill_match_fast(self, employee, shift):
        if not shift.required_skill_id:
            return True, 1.0
        score = self.skill_lookup.get((employee.id, shift.required_skill_id))
        if score is not None:
            return True, score
        return False, 0.0

    def _compute_score(self, employee, shift):
        # Hard Gate 1: Availability
        if not self._is_available_fast(employee, shift):
            return -1

        # Hard Gate 2: Skill Match
        has_skill, proficiency = self._get_skill_match_fast(employee, shift)
        if not has_skill:
            return -1

        # Fairness (using optimized counts)
        max_shifts = max(self.weekly_counts.values()) if self.weekly_counts else 1
        weekly_shifts = self.weekly_counts.get(employee.id, 0)
        fairness = 1.0 - normalize(weekly_shifts, 0, max_shifts)

        # Cost
        salaries = [float(e.salary) for e in self.all_employees]
        min_salary = min(salaries) if salaries else 0
        max_salary = max(salaries) if salaries else 1
        cost = 1.0 - normalize(float(employee.salary), min_salary, max_salary)

        score = (
            self.weights.get("availability", 0.30) * 1.0        +
            self.weights.get("skill_match", 0.25)  * 1.0        +
            self.weights.get("fairness", 0.20)     * fairness    +
            self.weights.get("skill_level", 0.15)  * proficiency +
            self.weights.get("cost", 0.10)         * cost
        )
        return round(score, 4)

    def _rank_employees(self, shift):
        rankings = []
        for emp in self.all_employees:
            score = self._compute_score(emp, shift)
            if score >= 0:
                rankings.append((emp, score))
        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def schedule_shifts_greedy(self):
        for shift in self.shifts: # Already ordered in __init__
            rankings = self._rank_employees(shift)
            if rankings:
                best_employee, best_score = rankings[0]
                self.schedule.append({
                    "shift":    shift,
                    "employee": best_employee,
                    "score":    best_score,
                    "rankings": rankings
                })
                # Update local weekly count for fairness in next iteration
                self.weekly_counts[best_employee.id] += 1
            else:
                self.unscheduled.append(shift)

        return self.schedule, self.unscheduled

    def apply_schedule(self):
        applied = []
        for entry in self.schedule:
            shift    = entry["shift"]
            employee = entry["employee"]

            shift.assigned_employee = employee
            shift.is_scheduled      = True
            shift.save()

            EmployeeSchedule.objects.get_or_create(
                employee   = employee,
                date       = shift.shift_date,
                start_time = shift.start_time,
                end_time   = shift.end_time,
            )
            applied.append({
                "shift_id":   shift.id,
                "shift_date": str(shift.shift_date),
                "start_time": str(shift.start_time),
                "end_time":   str(shift.end_time),
                "assigned":   employee.name,
                "score":      entry["score"],
                "rankings": [
        {"employee": e.name, "employee_id": e.id, "score": s}
        for e, s in entry.get("all_rankings", [])
    ],
            })

        return {
            "scheduled_count":   len(applied),
            "unscheduled_count": len(self.unscheduled),
            "total_shifts":      len(self.schedule) + len(self.unscheduled),
            "success_rate":      f"{(len(applied) / (len(applied) + len(self.unscheduled)) * 100):.2f}%"
                                 if (applied or self.unscheduled) else "0%",
            "assignments":       applied,
        }

    def get_schedule_summary(self):
        summary = {}
        for entry in self.schedule:
            emp_name = entry["employee"].name
            if emp_name not in summary:
                summary[emp_name] = {
                    "employee":       emp_name,
                    "shifts_assigned": 0,
                    "shift_dates":    [],
                    "avg_score":      0,
                    "scores":         [],
                }
            summary[emp_name]["shifts_assigned"] += 1
            summary[emp_name]["shift_dates"].append(str(entry["shift"].shift_date))
            summary[emp_name]["scores"].append(entry["score"])

        # Calculate average score per employee
        for emp in summary.values():
            emp["avg_score"] = round(
                sum(emp["scores"]) / len(emp["scores"]), 4
            )
            del emp["scores"]  # clean up before returning

        return {
            "total_scheduled":   len(self.schedule),
            "total_unscheduled": len(self.unscheduled),
            "unscheduled_shift_ids": [s.id for s in self.unscheduled],
            "employee_summary":  list(summary.values()),
        }