"""
Course Scheduler GUI — Right panel scrollable with Course Groups
- Python 3.8+
- No external libraries
- Load CSV or paste clipboard, add required courses, create course groups,
  lock sections, set min/max credits, run scheduler in background.
"""

import queue
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import csv
import io
from dataclasses import dataclass
from datetime import datetime
from collections import defaultdict
from typing import List, Dict, Optional
import io, csv, threading, queue

DAY_CHARS = set("MTWRFS")

def parse_time(t: str) -> Optional[int]:
    if not t:
        return None
    t = t.strip()
    if t == "":
        return None
    fmts = ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M")
    for fmt in fmts:
        try:
            dt = datetime.strptime(t, fmt)
            return dt.hour * 60 + dt.minute
        except Exception:
            continue
    try:
        if t[-2:].upper() in ("AM","PM"):
            dt = datetime.strptime(t, "%I%p")
            return dt.hour * 60
    except Exception:
        pass
    return None

def parse_days(s: str) -> List[str]:
    if not s:
        return []
    return [c for c in s.strip() if c in DAY_CHARS]

def minutes_to_str(m: Optional[int]) -> str:
    if m is None:
        return ""
    hour = m // 60
    minute = m % 60
    ampm = "AM" if hour < 12 else "PM"
    h = hour % 12
    if h == 0:
        h = 12
    return f"{h}:{minute:02d} {ampm}"

def get_course_title(section: "Section") -> str:
    """Get the course title from a section's raw data"""
    return section.raw.get("Course Title", "")

def format_course_display(course_code: str, sections: List["Section"], max_length: int = 50) -> str:
    """Format course code with title for display, truncating if too long"""
    if not sections:
        return course_code
    
    title = get_course_title(sections[0])  # Get title from first section
    if not title:
        return course_code
    
    # Format as "CODE (Title)"
    display = f"{course_code} ({title})"
    
    # Truncate if too long
    if len(display) > max_length:
        # Keep the course code and truncate the title
        available_for_title = max_length - len(course_code) - 4  # Account for " (...)"
        if available_for_title > 10:  # Only truncate if we have reasonable space
            truncated_title = title[:available_for_title-3] + "..."
            display = f"{course_code} ({truncated_title})"
        else:
            display = course_code  # Fall back to just the code
    
    return display

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated"""
    if len(text) <= max_length:
        return text
    return text[:max_length-len(suffix)] + suffix

@dataclass
class Section:
    course: str
    sec: str
    faculty: str
    days: List[str]
    start: Optional[int]
    end: Optional[int]
    credits: float
    raw: Dict

@dataclass
class CourseGroup:
    name: str
    courses: List[str]
    num_required: int

def check_time_requirements(s: Section, day_time_prefs: Dict[str,Dict]) -> bool:
    """Check if a section meets all time requirements (hard constraints)"""
    if not s.days or s.start is None:
        return True  # No time data, can't enforce requirements
    
    for day in s.days:
        if day in day_time_prefs and day_time_prefs[day]['enabled'] and day_time_prefs[day]['is_requirement']:
            day_pref = day_time_prefs[day]
            
            # Parse requirement times
            req_start = parse_time_to_minutes(day_pref['start_time'])
            req_end = parse_time_to_minutes(day_pref['end_time'])
            
            if req_start is not None and req_end is not None:
                section_start = s.start
                section_end = s.end or (s.start + 60)  # Assume 1 hour if no end time
                
                # Check if section is within required time range
                if not (section_start >= req_start and section_end <= req_end):
                    return False  # Violates time requirement
    
    return True  # All requirements satisfied

def overlaps(a: Section, b: Section) -> bool:
    if not a.days or not b.days or a.start is None or b.start is None:
        return False
    if set(a.days).isdisjoint(set(b.days)):
        return False
    return (a.start < b.end) and (b.start < a.end)

def score_section(s: Section, course_pref_faculty: Dict[str,str], day_time_prefs: Dict[str,Dict]) -> float:
    score = 0.0
    pref = course_pref_faculty.get(s.course)
    if pref and pref.strip().lower() == s.faculty.strip().lower():
        score += 100.0
    
    # Enhanced time preference scoring
    if s.start is not None and s.days:
        for day in s.days:
            if day in day_time_prefs and day_time_prefs[day]['enabled']:
                day_pref = day_time_prefs[day]
                
                # Parse preference times
                pref_start = parse_time_to_minutes(day_pref['start_time'])
                pref_end = parse_time_to_minutes(day_pref['end_time'])
                
                if pref_start is not None and pref_end is not None:
                    # Check if section time overlaps with preferred time
                    section_start = s.start
                    section_end = s.end or (s.start + 60)  # Assume 1 hour if no end time
                    
                    # Calculate overlap
                    overlap_start = max(section_start, pref_start)
                    overlap_end = min(section_end, pref_end)
                    
                    if overlap_start < overlap_end:  # There is overlap
                        overlap_duration = overlap_end - overlap_start
                        section_duration = section_end - section_start
                        overlap_ratio = overlap_duration / section_duration if section_duration > 0 else 0
                        
                        if day_pref['is_requirement']:
                            # For requirements, give high bonus for full compliance
                            if overlap_ratio >= 0.95:  # Nearly full overlap
                                score += 50.0
                            else:
                                # Partial overlap for requirements gets some points but less
                                score += 25.0 * overlap_ratio
                        else:
                            # For preferences, give proportional bonus
                            score += 30.0 * overlap_ratio
                    else:
                        # No overlap - penalty for requirements
                        if day_pref['is_requirement']:
                            score -= 200.0  # Heavy penalty for violating requirements
    
    return score

def parse_time_to_minutes(time_str: str) -> Optional[int]:
    """Convert time string (e.g., '02:30 PM') to minutes since midnight"""
    try:
        time_part, ampm = time_str.strip().split()
        hour, minute = map(int, time_part.split(':'))
        
        if ampm.upper() == 'PM' and hour != 12:
            hour += 12
        elif ampm.upper() == 'AM' and hour == 12:
            hour = 0
            
        return hour * 60 + minute
    except:
        return parse_time(time_str)  # Fallback to original parser

def gap_penalty(chosen: List[Section]) -> float:
    penalty = 0.0
    by_day = defaultdict(list)
    for s in chosen:
        if s.start is None: continue
        for d in s.days:
            by_day[d].append((s.start, s.end))
    for intervals in by_day.values():
        intervals.sort()
        for i in range(len(intervals)-1):
            gap = intervals[i+1][0] - intervals[i][1]
            if gap > 0:
                penalty += gap * 0.2
    return penalty

def find_best_schedule(sections: List[Section],
                             required_courses: List[str],
                             course_groups: List[CourseGroup],
                             faculty_prefs: Dict[str,str],
                             day_time_prefs: Dict[str,Dict],
                             locked_sections: List[Section],
                             min_credits: float,
                             max_credits: float,
                             callback=None):

    from collections import defaultdict

    # --- Preprocess: group sections by course ---
    by_course = defaultdict(list)
    for s in sections:
        by_course[s.course].append(s)

    # Include locked sections in required courses
    req_set = set(required_courses)
    for ls in locked_sections:
        req_set.add(ls.course)
    required_courses = list(req_set)

    # Restrict locked courses to the locked section only
    for ls in locked_sections:
        by_course[ls.course] = [s for s in by_course[ls.course]
                                if s.sec == ls.sec and s.faculty == ls.faculty]

    # --- Pre-filter sections by hard time requirements ---
    filtered_sections = {}
    for c, secs in by_course.items():
        filtered_sections[c] = [s for s in secs if check_time_requirements(s, day_time_prefs)]

    # --- Build group constraints ---
    group_constraints = {}
    all_courses = list(required_courses)
    for group in course_groups:
        valid_courses = [c for c in group.courses if c not in required_courses and filtered_sections.get(c)]
        if valid_courses:
            group_constraints[group.name] = {
                'courses': valid_courses,
                'num_required': min(group.num_required, len(valid_courses))
            }
            all_courses.extend(valid_courses)

    # --- Order courses by number of options (fewest first) ---
    ordered_courses = sorted(set(all_courses), key=lambda c: len(filtered_sections.get(c, [])))

    # Map course -> type (required/group)
    course_info = {}
    for c in ordered_courses:
        if c in required_courses:
            course_info[c] = ('required', None)
        else:
            for gname, gdata in group_constraints.items():
                if c in gdata['courses']:
                    course_info[c] = ('group', gname)
                    break

    # Precompute max credits per course
    max_credits_by_course = {c: max((s.credits for s in filtered_sections.get(c, [])), default=0.0)
                             for c in ordered_courses}

    # Initialize best schedule
    best = {"score": -1e9, "schedule": None, "credits": 0.0}
    initial_chosen = locked_sections.copy()
    initial_credits = sum(s.credits for s in initial_chosen)
    initial_score = sum(score_section(s, faculty_prefs, day_time_prefs) for s in initial_chosen)

    # --- Helper: check overlaps quickly using occupied minutes per day ---
    def add_to_schedule_grid(s, grid):
        for d in s.days:
            grid[d].update(range(s.start, s.end))
    
    def remove_from_schedule_grid(s, grid):
        for d in s.days:
            for m in range(s.start, s.end):
                grid[d].remove(m)
    
    def is_overlap(s, grid):
        for d in s.days:
            if any(m in grid[d] for m in range(s.start, s.end)):
                return True
        return False

    # --- Backtracking with in-place group_counts and grid ---
    def backtrack(idx, chosen, current_score, current_credits, group_counts, grid):
        if current_credits > max_credits:
            return
        if idx == len(ordered_courses):
            # Check group constraints
            if all(group_counts.get(g, 0) >= group_constraints[g]['num_required'] for g in group_constraints):
                if current_credits >= min_credits:
                    total_score = current_score - gap_penalty(chosen)
                    if total_score > best["score"]:
                        best["score"] = total_score
                        best["schedule"] = chosen.copy()
                        best["credits"] = current_credits
                        if callback:
                            callback("best", "SOLUTION FOUND", None, total_score, chosen)
            return

        course = ordered_courses[idx]
        ctype, gname = course_info[course]
        opts = filtered_sections.get(course, [])

        # Option 1: Skip course if allowed
        can_skip = True
        if ctype == 'required':
            can_skip = False
        elif ctype == 'group':
            needed = group_constraints[gname]['num_required'] - group_counts.get(gname, 0)
            remaining = sum(1 for c2 in ordered_courses[idx+1:] if c2 in group_constraints[gname]['courses'])
            if remaining < needed:
                can_skip = False
        if can_skip:
            remaining_max = sum(max_credits_by_course.get(c, 0.0) for c in ordered_courses[idx+1:])
            if current_credits + remaining_max >= min_credits:
                if callback:
                    callback("skip", course, None, current_score, chosen)
                backtrack(idx+1, chosen, current_score, current_credits, group_counts, grid)

        # Option 2: Take each section
        for s in opts:
            if is_overlap(s, grid):
                continue
            new_credits = current_credits + s.credits
            if new_credits > max_credits:
                continue

            # Update group_counts
            if ctype == 'group':
                if group_counts.get(gname, 0) >= group_constraints[gname]['num_required']:
                    continue
                group_counts[gname] = group_counts.get(gname, 0) + 1

            # Place in grid
            add_to_schedule_grid(s, grid)
            chosen.append(s)
            s_score = score_section(s, faculty_prefs, day_time_prefs)

            if callback:
                callback("try", s.course, s, current_score + s_score, chosen)

            backtrack(idx+1, chosen, current_score + s_score, new_credits, group_counts, grid)

            # Backtrack
            chosen.pop()
            remove_from_schedule_grid(s, grid)
            if ctype == 'group':
                group_counts[gname] -= 1
                if group_counts[gname] == 0:
                    del group_counts[gname]

    # Initialize grid and group_counts
    grid = defaultdict(set)
    for s in initial_chosen:
        add_to_schedule_grid(s, grid)
    group_counts = {}
    for s in initial_chosen:
        ctype, gname = course_info.get(s.course, ('required', None))
        if ctype == 'group':
            group_counts[gname] = group_counts.get(gname, 0) + 1

    backtrack(0, initial_chosen.copy(), initial_score, initial_credits, group_counts, grid)
    return best

class Visualizer:
    def __init__(self, root):
        self.window = tk.Toplevel(root)
        self.window.title("Schedule Visualization")
        self.window.geometry("800x600")
        
        # Control panel
        control_frame = ttk.Frame(self.window)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        ttk.Label(control_frame, text="Speed:").pack(side="left")
        self.delay_var = tk.DoubleVar(value=0.1)
        ttk.Scale(control_frame, from_=0.01, to=1.0, variable=self.delay_var, orient="horizontal").pack(side="left", fill="x", expand=True, padx=5)
        
        self.status_label = ttk.Label(control_frame, text="Initializing...")
        self.status_label.pack(side="right")

        # Canvas for drawing
        self.canvas = tk.Canvas(self.window, bg="white")
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.days = ['M', 'T', 'W', 'R', 'F', 'S']
        self.day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
        self.start_hour = 7
        self.end_hour = 22
        self.hour_height = 30
        self.day_width = 100
        self.margin_left = 60
        self.margin_top = 30
        
        self.colors = ["#FFB3BA", "#BAFFC9", "#BAE1FF", "#FFFFBA", "#FFDFBA", "#E0BBE4", "#957DAD", "#D291BC", "#FEC8D8", "#FFDFD3"]
        self.course_colors = {}

    def draw_grid(self):
        self.canvas.delete("all")
        
        # Draw time labels
        for h in range(self.start_hour, self.end_hour + 1):
            y = self.margin_top + (h - self.start_hour) * self.hour_height
            self.canvas.create_text(self.margin_left - 10, y, text=f"{h}:00", anchor="e")
            self.canvas.create_line(self.margin_left, y, self.margin_left + len(self.days) * self.day_width, y, fill="#ddd")
            
        # Draw day labels and vertical lines
        for i, day in enumerate(self.day_labels):
            x = self.margin_left + i * self.day_width
            self.canvas.create_text(x + self.day_width/2, self.margin_top - 15, text=day)
            self.canvas.create_line(x, self.margin_top, x, self.margin_top + (self.end_hour - self.start_hour) * self.hour_height, fill="#ddd")
            
        # Right border
        x = self.margin_left + len(self.days) * self.day_width
        self.canvas.create_line(x, self.margin_top, x, self.margin_top + (self.end_hour - self.start_hour) * self.hour_height, fill="#ddd")

    def get_color(self, course):
        if course not in self.course_colors:
            self.course_colors[course] = self.colors[len(self.course_colors) % len(self.colors)]
        return self.course_colors[course]

    def update_schedule(self, schedule, current_action, current_course, current_score):
        self.draw_grid()
        
        # Enhanced status display based on action type
        if current_action == "best":
            self.status_label.config(text=f"🎉 NEW BEST SOLUTION FOUND! | Score: {current_score:.1f} | Courses: {len(schedule)}")
        elif current_action == "FINAL":
            self.status_label.config(text=f"✅ FINAL SOLUTION | Score: {current_score:.1f} | Courses: {len(schedule)} | COMPLETE!")
        elif current_action == "try":
            self.status_label.config(text=f"Trying: {current_course} | Score: {current_score:.1f}")
        elif current_action == "skip":
            self.status_label.config(text=f"Skipping: {current_course} | Score: {current_score:.1f}")
        else:
            self.status_label.config(text=f"Action: {current_action} | Course: {current_course} | Score: {current_score:.1f}")
        
        for s in schedule:
            color = self.get_color(s.course)
            if s.start is None or s.end is None: continue
            
            start_h = s.start / 60
            end_h = s.end / 60
            
            # Clamp to visible range
            start_h = max(self.start_hour, start_h)
            end_h = min(self.end_hour, end_h)
            
            if start_h >= end_h: continue

            y1 = self.margin_top + (start_h - self.start_hour) * self.hour_height
            y2 = self.margin_top + (end_h - self.start_hour) * self.hour_height
            
            for day in s.days:
                if day in self.days:
                    idx = self.days.index(day)
                    x1 = self.margin_left + idx * self.day_width
                    x2 = x1 + self.day_width
                    
                    # Use different outline for best and final solutions
                    if current_action == "best":
                        outline_color = "red"
                        outline_width = 3
                    elif current_action == "FINAL":
                        outline_color = "green"
                        outline_width = 4
                    else:
                        outline_color = "gray"
                        outline_width = 1
                    
                    self.canvas.create_rectangle(x1 + 2, y1, x2 - 2, y2, fill=color, outline=outline_color, width=outline_width)
                    
                    # Create course display text with title
                    title = get_course_title(s)
                    if title:
                        # Truncate title to fit in the box
                        title_truncated = truncate_text(title, 15)
                        display_text = f"{s.course}\n{title_truncated}\nSec: {s.sec}"
                    else:
                        display_text = f"{s.course}\nSec: {s.sec}"
                    
                    self.canvas.create_text(x1 + 5, y1 + 5, text=display_text, anchor="nw", font=("Arial", 7), width=self.day_width-10)
        
        self.window.update() 

# ---------------- GUI ----------------

class SchedulerGUI:
    def __init__(self, root):
        self.root = root
        root.title("Course Scheduler with Groups")
        root.geometry("1200x700")
        self.sections: List[Section] = []
        self.required_courses: List[str] = []
        self.course_groups: List[CourseGroup] = []
        self.faculty_prefs: Dict[str,str] = {}
        self.locked_sections: List[Section] = []
        self.time_pref = tk.StringVar(value="any")
        # Enhanced time preferences system
        self.day_time_prefs = {
            'M': {'enabled': False, 'start_time': '08:00 AM', 'end_time': '05:00 PM', 'is_requirement': False},
            'T': {'enabled': False, 'start_time': '08:00 AM', 'end_time': '05:00 PM', 'is_requirement': False},
            'W': {'enabled': False, 'start_time': '08:00 AM', 'end_time': '05:00 PM', 'is_requirement': False},
            'R': {'enabled': False, 'start_time': '08:00 AM', 'end_time': '05:00 PM', 'is_requirement': False},
            'F': {'enabled': False, 'start_time': '08:00 AM', 'end_time': '05:00 PM', 'is_requirement': False},
            'S': {'enabled': False, 'start_time': '08:00 AM', 'end_time': '05:00 PM', 'is_requirement': False}
        }
        self.result_queue = queue.Queue()
        self.current_selected_course = None  # Track selected course for faculty preferences
        self.current_selected_group_index = None  # Track selected group for course management
        self.current_req_selection = None  # Track required course selection index
        self._build_ui() 

    def _build_ui(self):
        # Add status bar at top
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=10, pady=(10,0))
        
        ttk.Label(status_frame, text="📚 Course Scheduler", font=("Arial", 12, "bold")).pack(side="left")
        self.status_label = ttk.Label(status_frame, text="Ready - Load course data to begin", foreground="blue")
        self.status_label.pack(side="right")
        
        self.paned = ttk.Panedwindow(self.root, orient="horizontal")
        self.paned.pack(fill="both", expand=True, padx=10, pady=10)

        left = ttk.Frame(self.paned)
        self.paned.add(left, weight=3)

        # Enhanced toolbar with better grouping
        toolbar = ttk.LabelFrame(left, text="📊 Course Data Management")
        toolbar.pack(fill="x", padx=6, pady=6)
        
        # Data loading buttons
        load_frame = ttk.Frame(toolbar)
        load_frame.pack(fill="x", padx=6, pady=6)
        ttk.Label(load_frame, text="Step 1: Load Data", font=("Arial", 9, "bold")).pack(anchor="w")
        
        btn_frame = ttk.Frame(load_frame)
        btn_frame.pack(fill="x", pady=(4,0))
        ttk.Button(btn_frame, text="📁 Open CSV File", command=self._open_csv).pack(side="left", padx=4)
           
        # Filter section
        filter_frame = ttk.Frame(load_frame)
        filter_frame.pack(fill="x", pady=(8,4))
        ttk.Label(filter_frame, text="Filter courses:").pack(side="left")
        self.filter_var = tk.StringVar()
        ent = ttk.Entry(filter_frame, textvariable=self.filter_var, width=30)
        ent.pack(side="left", padx=(8,4))
        ent.bind("<KeyRelease>", lambda e: self._refresh_table())
        ttk.Label(filter_frame, text="(Search by course, faculty, or title, or remark)", foreground="gray").pack(side="left", padx=(4,0))

        # Data validation indicator
        self.data_status_frame = ttk.Frame(toolbar)
        self.data_status_frame.pack(fill="x", pady=(4,0))
        self.data_status_label = ttk.Label(self.data_status_frame, text="❌ No course data loaded")
        self.data_status_label.pack(anchor="w")

        # Table container for correct scrollbar layout
        table_frame = ttk.Frame(left)
        table_frame.pack(fill="both", expand=True, padx=6, pady=(6,6))

        cols = ("Course","Sec","Title","CR","Faculty","Days","Start","End","Room","Remarks")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="extended")
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=100, anchor="w")
        self.tree.column("Title", width=260)
        self.tree.column("Faculty", width=160)
        
        # Add scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscroll=vsb.set, xscroll=hsb.set)
        
        # Grid layout for table and scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self._make_tree_context_menu()

        # Instructions for table interaction
        help_frame = ttk.Frame(left)
        help_frame.pack(fill="x", padx=6, pady=(0,6))
        ttk.Label(help_frame, text="💡 Tip: Double-click a course to add it as required, or right-click for more options", 
                 foreground="gray", font=("Arial", 8)).pack(anchor="w")

        # Right pane: make it scrollable using Canvas
        right_container = ttk.Frame(self.paned)
        self.paned.add(right_container, weight=2)

        canvas = tk.Canvas(right_container, borderwidth=0)
        vscroll = ttk.Scrollbar(right_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vscroll.set)

        vscroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.right_inner = ttk.Frame(canvas)
        self.right_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self._canvas_window = canvas.create_window((0,0), window=self.right_inner, anchor="nw")

        def _on_canvas_config(event):
            canvas.itemconfig(self._canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_config)

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            else:
                canvas.yview_scroll(-1 * (event.delta // 120), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        # Required courses with step indicator
        req_frame = ttk.LabelFrame(self.right_inner, text="📝 Step 2: Select Required Courses", padding=8)
        req_frame.pack(fill="x", padx=6, pady=6)
        
        # Instructions
        ttk.Label(req_frame, text="Choose courses that you must take:", 
                 font=("Arial", 9), foreground="gray").pack(anchor="w", pady=(0,4))
        
        # Required courses list with status
        req_container = ttk.Frame(req_frame)
        req_container.pack(fill="x")
        
        req_list_frame = ttk.Frame(req_container)
        req_list_frame.pack(side="left", fill="both", expand=True)
        
        self.req_listbox = tk.Listbox(req_list_frame, height=8)
        self.req_listbox.pack(fill="x")
        
        # Status indicator for required courses
        self.req_status_frame = ttk.Frame(req_list_frame)
        self.req_status_frame.pack(fill="x", pady=(4,0))
        self.req_status_label = ttk.Label(self.req_status_frame, text="0 required courses selected")
        self.req_status_label.pack(anchor="w")
        
        # Control buttons
        btns = ttk.Frame(req_container)
        btns.pack(side="right", padx=(8,0))
        ttk.Button(btns, text="➕ Add Selected", command=self._add_selected_required).pack(fill="x", pady=2)
        ttk.Button(btns, text="➖ Remove", command=self._remove_selected_required).pack(fill="x", pady=2)
        ttk.Button(btns, text="🗑️ Clear All", command=self._clear_required).pack(fill="x", pady=2)

        # Course Groups with enhanced UI
        groups_frame = ttk.LabelFrame(self.right_inner, text="Step 3: Create Course Groups (Optional)", padding=8)
        groups_frame.pack(fill="x", padx=6, pady=6)
        
        # Instructions
        ttk.Label(groups_frame, text="Create groups of courses (e.g., '2 from Hard Stuff that\nI am afraid to take more than two of them'):", 
             font=("Arial", 9), foreground="gray").pack(anchor="w", pady=(0,4))
        # Group creation form
        create_frame = ttk.LabelFrame(groups_frame, text="Create New Group")
        create_frame.pack(fill="x", pady=(0,8))
        
        form_container = ttk.Frame(create_frame)
        form_container.pack(fill="x", padx=8, pady=8)
        
        ttk.Label(form_container, text="Group Name:").grid(row=0, column=0, sticky="w", padx=(0,4))
        self.group_name_entry = ttk.Entry(form_container)
        self.group_name_entry.grid(row=0, column=1, sticky="we", padx=4)
        
        ttk.Label(form_container, text="Courses Needed:").grid(row=0, column=2, sticky="w", padx=(8,4))
        self.group_count_spin = tk.Spinbox(form_container, from_=1, to=10, width=5)
        self.group_count_spin.grid(row=0, column=3, sticky="w", padx=4)
        self.group_count_spin.delete(0, "end")
        self.group_count_spin.insert(0, "1")
        
        create_btn = ttk.Button(form_container, text="✅ Create", command=self._create_group_enhanced)
        create_btn.grid(row=0, column=4, sticky="e", padx=(8,0))

        # Let the entry expand so the button stays visible
        form_container.columnconfigure(1, weight=1)
        form_container.columnconfigure(0, weight=0)
        form_container.columnconfigure(2, weight=0)
        form_container.columnconfigure(3, weight=0)
        form_container.columnconfigure(4, weight=0)
        
        
        # Management buttons in a separate row
        group_btns = ttk.Frame(groups_frame)
        group_btns.pack(fill="x", pady=(0,4))
        ttk.Button(group_btns, text="🗑️ Delete Group", command=self._delete_group).pack(side="right")
        
        # Groups list with status
        groups_container = ttk.Frame(groups_frame)
        groups_container.pack(fill="x")
        
        groups_left = ttk.Frame(groups_container)
        groups_left.pack(side="left", fill="both", expand=True)
        
        ttk.Label(groups_left, text="Your Course Groups:", font=("Arial", 9, "bold")).pack(anchor="w")
        self.groups_listbox = tk.Listbox(groups_left, height=6, bg="#f0f0f0", selectbackground="#4a90e2", exportselection=False)
        self.groups_listbox.pack(fill="x", pady=(2,4))
        self.groups_listbox.bind("<<ListboxSelect>>", self._on_group_select)
        
        # Group status with better visibility
        self.group_status_label = ttk.Label(groups_left, text="No groups created yet", font=("Arial", 8, "italic"))
        self.group_status_label.pack(anchor="w")
        
        # Selected group indicator
        self.selected_group_label = ttk.Label(groups_left, text="No group selected", 
                                            font=("Arial", 9, "bold"), foreground="#4a90e2")
        self.selected_group_label.pack(anchor="w", pady=(4,0))
        
        # Group courses management with enhanced UI
        groups_right = ttk.Frame(groups_container)
        groups_right.pack(side="right", padx=(8,0))
        
        # Header with instructions
        header_frame = ttk.Frame(groups_right)
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="Courses in Selected Group:", font=("Arial", 9, "bold")).pack(anchor="w")
        ttk.Label(header_frame, text="(Select courses below to remove them)", 
                 font=("Arial", 8), foreground="gray").pack(anchor="w")
        
        # Course list with better styling
        self.group_courses_listbox = tk.Listbox(groups_right, height=5, width=30, 
                                              bg="#f8f8f8", selectbackground="#ff6b6b",
                                              selectmode="extended", exportselection=False)
        self.group_courses_listbox.pack(pady=(4,8))
        
        # Bind selection event for better feedback
        self.group_courses_listbox.bind("<<ListboxSelect>>", self._on_group_course_select)
        
        # Enhanced button layout with better labels and icons
        group_course_btns = ttk.Frame(groups_right)
        group_course_btns.pack(fill="x")
        
        # Add courses button (from main table)
        add_btn = ttk.Button(group_course_btns, text="➕ Add Selected Courses", 
                           command=self._add_to_group, style="Accent.TButton")
        add_btn.pack(fill="x", pady=(0,4))
        
        # Remove courses button (from group list)
        self.remove_btn = ttk.Button(group_course_btns, text="🗑️ Remove Selected", 
                                   command=self._remove_from_group_enhanced, state="disabled")
        self.remove_btn.pack(fill="x", pady=(0,4))
        
        # Quick action buttons
        quick_frame = ttk.Frame(group_course_btns)
        quick_frame.pack(fill="x", pady=(4,0))
        
        ttk.Button(quick_frame, text="Clear All", command=self._clear_group_courses).pack(side="left", fill="x", expand=True, padx=(0,2))
        ttk.Button(quick_frame, text="Select All", command=self._select_all_group_courses).pack(side="left", fill="x", expand=True, padx=(2,0))
        
        # Status display for course operations
        self.course_op_status = ttk.Label(groups_right, text="Select a group to manage its courses", 
                                        font=("Arial", 8), foreground="gray")
        self.course_op_status.pack(pady=(8,0))

        # Faculty preference with better layout
        pref_frame = ttk.LabelFrame(self.right_inner, text="⭐ Step 4: Set Faculty Preferences (Optional)", padding=8)
        pref_frame.pack(fill="x", padx=6, pady=6)
        
        ttk.Label(pref_frame, text="Choose preferred faculty for courses with multiple instructors:", 
                 font=("Arial", 9), foreground="gray").pack(anchor="w", pady=(0,4))
        
        pref_container = ttk.Frame(pref_frame)
        pref_container.pack(fill="x")
         
        ttk.Label(pref_container, text="Course:").pack(anchor="w")
        self.course_combo = ttk.Combobox(pref_container, state="readonly", width=30)
        self.course_combo.pack(fill="x", pady=(2,4))
        self.course_combo.bind("<<ComboboxSelected>>", self._on_course_combo_select)
        
        ttk.Label(pref_container, text="Preferred Faculty:").pack(anchor="w")
        self.faculty_combo = ttk.Combobox(pref_container, state="readonly", width=30)
        self.faculty_combo.pack(fill="x", pady=(2,4))
        
        # Prevent combobox from clearing course selection
        self.faculty_combo.bind("<Button-1>", self._on_faculty_click)
        self.faculty_combo.bind("<<ComboboxSelected>>", self._on_faculty_selected)
        
        pref_btn_frame = ttk.Frame(pref_container)
        pref_btn_frame.pack(fill="x")
        ttk.Button(pref_btn_frame, text="✅ Set Preference", command=self._set_fac_pref_new).pack(side="left")
        self.pref_status_label = ttk.Label(pref_btn_frame, text="Select a course first", foreground="gray")
        self.pref_status_label.pack(side="right")
        
        # Show current preferences
        self.prefs_display = tk.Text(pref_container, height=3, width=50)
        self.prefs_display.pack(fill="x", pady=(8,0))
        self.prefs_display.config(state="disabled")
        
        # Add explanatory note
        note_frame = ttk.Frame(pref_container)
        note_frame.pack(fill="x", pady=(4,0))
        ttk.Label(note_frame, text="💡 Note: Only courses with multiple faculty options are shown above.", 
                 font=("Arial", 8), foreground="gray").pack(anchor="w")
        ttk.Label(note_frame, text="Courses with only one instructor don't need preference settings.", 
                 font=("Arial", 8), foreground="gray").pack(anchor="w")
        
        # Remove the problematic focus handlers that cause conflicts
        # Update course combo when required courses change
        self._update_course_combo()

        # Time preference and credits with step indicator
        run_frame = ttk.LabelFrame(self.right_inner, text="⚙️ Step 5: Configure Schedule Preferences", padding=8)
        run_frame.pack(fill="x", padx=6, pady=6)
        
        # Enhanced time preferences with day-by-day customization
        time_frame = ttk.LabelFrame(run_frame, text="Time Preferences by Day")
        time_frame.pack(fill="x", pady=(0,8))
        
        # Instructions
        instr_frame = ttk.Frame(time_frame)
        instr_frame.pack(fill="x", padx=8, pady=(8,4))
        ttk.Label(instr_frame, text="Set time preferences for specific days (Sunday excluded):", 
                 font=("Arial", 9), foreground="gray").pack(anchor="w")
        ttk.Label(instr_frame, text="• Preference: Scheduler will try to respect this time range but may ignore if needed", 
                 font=("Arial", 8), foreground="gray").pack(anchor="w")
        ttk.Label(instr_frame, text="• Requirement: Scheduler will ONLY schedule classes within this time range", 
                 font=("Arial", 8), foreground="gray").pack(anchor="w")
        
        # Create scrollable frame for day preferences
        time_container = ttk.Frame(time_frame)
        time_container.pack(fill="x", padx=8, pady=8)
        
        # Day names
        day_names = {
            'M': 'Monday',
            'T': 'Tuesday', 
            'W': 'Wednesday',
            'R': 'Thursday',
            'F': 'Friday',
            'S': 'Saturday'
        }
        
        # Create UI elements for each day
        self.day_widgets = {}
        
        for i, (day_code, day_name) in enumerate(day_names.items()):
            day_frame = ttk.LabelFrame(time_container, text=day_name)
            day_frame.grid(row=i//2, column=i%2, sticky="ew", padx=4, pady=4)
            
            # Enable checkbox
            enabled_var = tk.BooleanVar(value=self.day_time_prefs[day_code]['enabled'])
            enabled_check = ttk.Checkbutton(day_frame, text="Set time preference", 
                                          variable=enabled_var,
                                          command=lambda dc=day_code: self._on_day_enabled_changed(dc))
            enabled_check.pack(anchor="w", padx=4, pady=2)
            
            # Time range frame
            time_range_frame = ttk.Frame(day_frame)
            time_range_frame.pack(fill="x", padx=4, pady=2)
            
            # Start time
            ttk.Label(time_range_frame, text="From:").grid(row=0, column=0, sticky="w")
            start_var = tk.StringVar(value=self.day_time_prefs[day_code]['start_time'])
            start_spin = tk.Spinbox(time_range_frame, textvariable=start_var, width=8,
                                   values=self._generate_time_options())
            start_spin.grid(row=0, column=1, padx=2)
            
            # End time
            ttk.Label(time_range_frame, text="To:").grid(row=0, column=2, sticky="w", padx=(8,0))
            end_var = tk.StringVar(value=self.day_time_prefs[day_code]['end_time'])
            end_spin = tk.Spinbox(time_range_frame, textvariable=end_var, width=8,
                                 values=self._generate_time_options())
            end_spin.grid(row=0, column=3, padx=2)
            
            # Preference type
            pref_frame = ttk.Frame(day_frame)
            pref_frame.pack(fill="x", padx=4, pady=2)
            
            req_var = tk.BooleanVar(value=self.day_time_prefs[day_code]['is_requirement'])
            pref_radio = ttk.Radiobutton(pref_frame, text="Preference", 
                                       variable=req_var, value=False)
            pref_radio.pack(side="left")
            
            req_radio = ttk.Radiobutton(pref_frame, text="Requirement", 
                                      variable=req_var, value=True)
            req_radio.pack(side="left", padx=(8,0))
            
            # Store widgets for later access
            self.day_widgets[day_code] = {
                'enabled_var': enabled_var,
                'start_var': start_var,
                'end_var': end_var,
                'req_var': req_var,
                'start_spin': start_spin,
                'end_spin': end_spin,
                'pref_radio': pref_radio,
                'req_radio': req_radio,
                'time_range_frame': time_range_frame,
                'pref_frame': pref_frame
            }
            
            # Initially disable time controls if not enabled
            self._update_day_controls(day_code)
        
        # Configure grid weights for responsive layout
        time_container.columnconfigure(0, weight=1)
        time_container.columnconfigure(1, weight=1)
        
        # Apply/Reset buttons for time preferences
        time_btn_frame = ttk.Frame(time_frame)
        time_btn_frame.pack(fill="x", padx=8, pady=(4,8))
        
        ttk.Button(time_btn_frame, text="✅ Apply Time Preferences", 
                  command=self._apply_time_preferences).pack(side="left")
        ttk.Button(time_btn_frame, text="🔄 Reset All", 
                  command=self._reset_time_preferences).pack(side="left", padx=(8,0))
        
        # Status for time preferences
        self.time_pref_status = ttk.Label(time_btn_frame, text="No time preferences set", 
                                        font=("Arial", 8), foreground="gray")
        self.time_pref_status.pack(side="right")
        
        # Credit range
        credits_frame = ttk.LabelFrame(run_frame, text="Credit Range")
        credits_frame.pack(fill="x", pady=(0,8))
        
        credits_container = ttk.Frame(credits_frame)
        credits_container.pack(padx=8, pady=8)
        
        credit_row1 = ttk.Frame(credits_container)
        credit_row1.pack(fill="x")
        
        ttk.Label(credit_row1, text="Minimum Credits:").pack(side="left")
        self.min_spin = tk.Spinbox(credit_row1, from_=0, to=60, width=5, command=self._update_credit_status)
        self.min_spin.pack(side="left", padx=(8,16))
        
        ttk.Label(credit_row1, text="Maximum Credits:").pack(side="left")
        self.max_spin = tk.Spinbox(credit_row1, from_=0, to=60, width=5, command=self._update_credit_status)
        self.max_spin.pack(side="left", padx=8)
        
        self.min_spin.delete(0, "end"); self.min_spin.insert(0, "12")
        self.max_spin.delete(0, "end"); self.max_spin.insert(0, "18")
        
        # Credit status
        self.credit_status_label = ttk.Label(credits_container, text="Credit range: 12-18")
        self.credit_status_label.pack(pady=(4,0))
        
        # Pre-flight checklist
        checklist_frame = ttk.LabelFrame(run_frame, text="Pre-flight Checklist")
        checklist_frame.pack(fill="x", pady=(0,8))
        
        self.checklist_container = ttk.Frame(checklist_frame)
        self.checklist_container.pack(padx=8, pady=8, fill="x")
        
        # Run button with progress
        run_container = ttk.Frame(run_frame)
        run_container.pack(fill="x")
        
        self.visualize_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(run_container, text="Visualize Algorithm", variable=self.visualize_var).pack(pady=(0,4))

        self.run_button = ttk.Button(run_container, text="🚀 Generate My Schedule", command=self._run_scheduler_threaded)
        self.run_button.pack(pady=8)
        
        self.progress = ttk.Progressbar(run_container, mode="indeterminate")
        self.progress.pack(fill="x", pady=(0,4))
        
        self.progress_label = ttk.Label(run_container, text="")
        self.progress_label.pack()

        # Locked sections with better explanation
        lock_frame = ttk.LabelFrame(self.right_inner, text="🔒 Locked Sections (Advanced)", padding=8)
        lock_frame.pack(fill="x", padx=6, pady=6)
        
        ttk.Label(lock_frame, text="Force specific sections into your schedule:", 
                 font=("Arial", 9), foreground="gray").pack(anchor="w", pady=(0,4))
        
        self.lock_listbox = tk.Listbox(lock_frame, height=4)
        self.lock_listbox.pack(fill="x", pady=(0,4))
        
        lock_btn_frame = ttk.Frame(lock_frame)
        lock_btn_frame.pack(fill="x")
        ttk.Button(lock_btn_frame, text="🔓 Remove Lock", command=self._remove_selected_lock).pack(side="left")
        ttk.Label(lock_btn_frame, text="Right-click courses in table to lock", 
                 foreground="gray", font=("Arial", 8)).pack(side="right")

        # Results with enhanced display
        res_frame = ttk.LabelFrame(self.right_inner, text="📋 Generated Schedule", padding=8)
        res_frame.pack(fill="both", expand=True, padx=6, pady=6)
        
        # Results header with status
        res_header = ttk.Frame(res_frame)
        res_header.pack(fill="x", pady=(0,4))
        self.result_status_label = ttk.Label(res_header, text="No schedule generated yet", foreground="gray")
        self.result_status_label.pack(anchor="w")
        
        # Results tree
        res_container = ttk.Frame(res_frame)
        res_container.pack(fill="both", expand=True)
        
        res_cols = ("Course","Title","Sec","Faculty","Days","Start","End","Room","Credits","Score")
        self.res_tree = ttk.Treeview(res_container, columns=res_cols, show="headings")
        for c in res_cols:
            self.res_tree.heading(c, text=c)
            self.res_tree.column(c, width=90, anchor="w")
        self.res_tree.column("Title", width=180)
        self.res_tree.column("Faculty", width=140)
        self.res_tree.pack(side="left", fill="both", expand=True)
        
        res_vsb = ttk.Scrollbar(res_container, orient="vertical", command=self.res_tree.yview)
        self.res_tree.configure(yscroll=res_vsb.set)
        res_vsb.pack(side="right", fill="y")
        
        # Export buttons
        export_frame = ttk.Frame(res_frame)
        export_frame.pack(fill="x", pady=(8,0))
        ttk.Button(export_frame, text="💾 Export to CSV", command=self._export_schedule).pack(side="left", padx=(0,4))
        ttk.Button(export_frame, text="🔍 Show Details", command=self._open_results_window).pack(side="left")

        self.root.after(200, self._poll_result_queue)
        
        # Initialize status displays
        self._update_checklist()
        self._update_data_status() 

    # ---------- Enhanced Time Preference Methods ----------
    def _generate_time_options(self):
        """Generate time options in 30-minute intervals from 7:00 AM to 10:00 PM"""
        times = []
        for hour in range(7, 22):  # 7 AM to 9 PM
            for minute in [0, 30]:
                if hour < 12:
                    ampm = "AM"
                    display_hour = hour if hour != 0 else 12
                else:
                    ampm = "PM" 
                    display_hour = hour if hour <= 12 else hour - 12
                time_str = f"{display_hour:02d}:{minute:02d} {ampm}"
                times.append(time_str)
        return times
    
    def _parse_time_preference(self, time_str):
        """Convert time string (e.g., '02:30 PM') to minutes since midnight"""
        try:
            time_part, ampm = time_str.strip().split()
            hour, minute = map(int, time_part.split(':'))
            
            if ampm.upper() == 'PM' and hour != 12:
                hour += 12
            elif ampm.upper() == 'AM' and hour == 12:
                hour = 0
                
            return hour * 60 + minute
        except:
            return None
    
    def _on_day_enabled_changed(self, day_code):
        """Handle when a day's time preference is enabled/disabled"""
        self._update_day_controls(day_code)
        self._update_time_pref_status()
    
    def _update_day_controls(self, day_code):
        """Enable/disable time controls based on enabled state"""
        widgets = self.day_widgets[day_code]
        enabled = widgets['enabled_var'].get()
        
        # Enable/disable time selection controls
        state = "normal" if enabled else "disabled"
        widgets['start_spin'].config(state=state)
        widgets['end_spin'].config(state=state)
        widgets['pref_radio'].config(state=state)
        widgets['req_radio'].config(state=state)
    
    def _apply_time_preferences(self):
        """Apply the current time preference settings"""
        applied_count = 0
        requirements_count = 0
        
        for day_code in self.day_time_prefs:
            widgets = self.day_widgets[day_code]
            enabled = widgets['enabled_var'].get()
            
            self.day_time_prefs[day_code] = {
                'enabled': enabled,
                'start_time': widgets['start_var'].get(),
                'end_time': widgets['end_var'].get(),
                'is_requirement': widgets['req_var'].get()
            }
            
            if enabled:
                applied_count += 1
                if widgets['req_var'].get():
                    requirements_count += 1
        
        self._update_time_pref_status()
        
        if applied_count > 0:
            if requirements_count > 0:
                self.status_label.config(text=f"✅ Applied {applied_count} time preferences ({requirements_count} requirements)", foreground="green")
            else:
                self.status_label.config(text=f"✅ Applied {applied_count} time preferences", foreground="green")
            self.root.after(3000, lambda: self.status_label.config(text="Ready to configure schedule", foreground="blue"))
        else:
            messagebox.showinfo("No Preferences", "No time preferences are currently enabled.")
    
    def _reset_time_preferences(self):
        """Reset all time preferences to default"""
        if messagebox.askyesno("Reset Time Preferences", "Reset all time preferences to default settings?"):
            for day_code in self.day_time_prefs:
                self.day_time_prefs[day_code] = {
                    'enabled': False,
                    'start_time': '08:00 AM',
                    'end_time': '05:00 PM',
                    'is_requirement': False
                }
                
                widgets = self.day_widgets[day_code]
                widgets['enabled_var'].set(False)
                widgets['start_var'].set('08:00 AM')
                widgets['end_var'].set('05:00 PM') 
                widgets['req_var'].set(False)
                self._update_day_controls(day_code)
            
            self._update_time_pref_status()
            self.status_label.config(text="Time preferences reset", foreground="blue")
    
    def _update_time_pref_status(self):
        """Update the status display for time preferences"""
        enabled_days = [day for day, prefs in self.day_time_prefs.items() if prefs['enabled']]
        requirements = [day for day, prefs in self.day_time_prefs.items() if prefs['enabled'] and prefs['is_requirement']]
        
        if not enabled_days:
            self.time_pref_status.config(text="No time preferences set", foreground="gray")
        else:
            day_names = {'M': 'Mon', 'T': 'Tue', 'W': 'Wed', 'R': 'Thu', 'F': 'Fri', 'S': 'Sat'}
            enabled_names = [day_names[d] for d in enabled_days]
            
            if requirements:
                req_names = [day_names[d] for d in requirements]
                status_text = f"✅ {len(enabled_days)} days set ({', '.join(enabled_names)})"
                if len(requirements) > 0:
                    status_text += f", {len(requirements)} required ({', '.join(req_names)})"
                self.time_pref_status.config(text=status_text, foreground="green")
            else:
                self.time_pref_status.config(text=f"✅ {len(enabled_days)} days set ({', '.join(enabled_names)})", foreground="blue")
    def _update_data_status(self):
        """Update data loading status indicator"""
        count = len(self.sections)
        if count == 0:
            self.data_status_label.config(text="❌ No course data loaded", foreground="red")
            self.status_label.config(text="Load course data to begin", foreground="red")
        else:
            self.data_status_label.config(text=f"✅ {count} courses loaded", foreground="green")
            self.status_label.config(text="Ready to configure schedule", foreground="blue")
        self._update_checklist()
    
    def _update_req_status(self):
        """Update required courses status"""
        count = len(self.required_courses)
        if count == 0:
            self.req_status_label.config(text="No required courses selected")
        else:
            self.req_status_label.config(text=f"✅ {count} required courses selected")
        self._update_checklist()
    
    def _update_group_status(self):
        """Update course groups status with enhanced information"""
        count = len(self.course_groups)
        if count == 0:
            self.group_status_label.config(text="No groups created yet", foreground="gray")
        else:
            total_needed = sum(g.num_required for g in self.course_groups)
            total_courses = sum(len(g.courses) for g in self.course_groups)
            
            # More detailed status
            if total_courses == 0:
                self.group_status_label.config(text=f"✅ {count} group(s) created, but no courses added yet", foreground="orange")
            else:
                self.group_status_label.config(text=f"✅ {count} group(s): need {total_needed} courses, have {total_courses} available", foreground="green")
    
    def _update_credit_status(self):
        """Update credit range status"""
        try:
            min_c = int(self.min_spin.get())
            max_c = int(self.max_spin.get())
            if min_c <= max_c:
                self.credit_status_label.config(text=f"✅ Credit range: {min_c}-{max_c}")
            else:
                self.credit_status_label.config(text="❌ Invalid range (min > max)")
        except:
            self.credit_status_label.config(text="❌ Invalid credit values")
        self._update_checklist()
    
    def _update_checklist(self):
        """Update the pre-flight checklist"""
        # Clear existing checklist
        for widget in self.checklist_container.winfo_children():
            widget.destroy()
        
        checks = []
        
        # Check data loaded
        if len(self.sections) > 0:
            checks.append(("✅", f"Course data loaded ({len(self.sections)} sections)", True))
        else:
            checks.append(("❌", "No course data loaded", False))
        
        # Check required courses or groups
        has_requirements = len(self.required_courses) > 0 or len(self.course_groups) > 0 or len(self.locked_sections) > 0
        if has_requirements:
            req_text = []
            if len(self.required_courses) > 0:
                req_text.append(f"{len(self.required_courses)} required")
            if len(self.course_groups) > 0:
                req_text.append(f"{len(self.course_groups)} groups")
            if len(self.locked_sections) > 0:
                req_text.append(f"{len(self.locked_sections)} locked")
            checks.append(("✅", f"Course selection: {', '.join(req_text)}", True))
        else:
            checks.append(("⚠️", "No courses or groups selected", False))
        
        # Check credit range
        try:
            min_c = int(self.min_spin.get())
            max_c = int(self.max_spin.get())
            if min_c <= max_c and min_c >= 0:
                checks.append(("✅", f"Credit range: {min_c}-{max_c}", True))
            else:
                checks.append(("❌", "Invalid credit range", False))
        except:
            checks.append(("❌", "Invalid credit values", False))
        
        # Display checklist
        all_good = True
        for icon, text, status in checks:
            if not status and "⚠️" not in icon:
                all_good = False
            item_label = ttk.Label(self.checklist_container, text=f"{icon} {text}")
            item_label.pack(anchor="w")
        
        # Update run button state
        can_run = all_good and has_requirements
        self.run_button.config(state="normal" if can_run else "disabled")
        
        if not can_run:
            if not has_requirements:
                self.progress_label.config(text="Add required courses or create groups to continue")
            else:
                self.progress_label.config(text="Fix issues above to continue")
        else:
            self.progress_label.config(text="Ready to generate schedule")
    
    def _create_group_enhanced(self):
        """Enhanced group creation with validation and feedback"""
        name = self.group_name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a group name")
            self.group_name_entry.focus()
            return
        
        try:
            count = int(self.group_count_spin.get())
            if count <= 0:
                raise ValueError()
        except:
            messagebox.showerror("Error", "Please enter a valid number greater than 0")
            self.group_count_spin.focus()
            return
        
        # Check if group already exists
        if any(g.name.lower() == name.lower() for g in self.course_groups):
            messagebox.showerror("Error", f"Group '{name}' already exists")
            self.group_name_entry.focus()
            return
        
        # Create group
        group = CourseGroup(name=name, courses=[], num_required=count)
        self.course_groups.append(group)
        
        # Clear form
        self.group_name_entry.delete(0, "end")
        self.group_count_spin.delete(0, "end")
        self.group_count_spin.insert(0, "1")
        
        # Update displays
        self._refresh_groups_listbox()
        self._update_group_status()
        self._update_checklist()
        
        # Show success feedback
        self.status_label.config(text=f"✅ Group '{name}' created successfully", foreground="green")
        self.root.after(3000, lambda: self.status_label.config(text="Ready to configure schedule", foreground="blue"))
        
        # Focus new group
        for i, g in enumerate(self.course_groups):
            if g.name == name:
                self.groups_listbox.selection_set(i)
                self._on_group_select(None)
                break

    # ---------- Course Groups Management ----------
    def _create_group(self):
        """Legacy method - redirect to enhanced version"""
        self._create_group_enhanced()
    
    def _delete_group(self):
        sel = self.groups_listbox.curselection()
        if not sel:
            messagebox.showinfo("Select Group", "Please select a group to delete.")
            return
        idx = sel[0]
        group = self.course_groups[idx]
        if messagebox.askyesno("Confirm Deletion", f"Delete group '{group.name}'?\n\nThis will remove the group and its course selections."):
            self.course_groups.pop(idx)
            self._refresh_groups_listbox()
            self.group_courses_listbox.delete(0, "end")
            
            # Update faculty preferences dropdown to reflect group deletion
            self._update_course_combo()
            
            self.status_label.config(text=f"Group '{group.name}' deleted", foreground="blue")
    
    def _refresh_groups_listbox(self):
        self.groups_listbox.delete(0, "end")
        for g in self.course_groups:
            display_text = f"{g.name} (need {g.num_required}"
            if len(g.courses) > 0:
                display_text += f", have {len(g.courses)})"
            else:
                display_text += ", no courses yet)"
            self.groups_listbox.insert("end", display_text)
        self._update_group_status()
    
    def _on_group_select(self, event):
        sel = self.groups_listbox.curselection()
        if not sel:
            # Only clear if this isn't a programmatic selection
            if event is not None:
                self.group_courses_listbox.delete(0, "end")
                self.current_selected_group_index = None
                self.selected_group_label.config(text="No group selected", foreground="gray")
                self.course_op_status.config(text="Select a group to manage its courses", foreground="gray")
                self.remove_btn.config(state="disabled")
            return
        idx = sel[0]
        self.current_selected_group_index = idx  # Store the selected group index
        group = self.course_groups[idx]
        
        # Update selected group display
        self.selected_group_label.config(text=f"Selected: {group.name}", foreground="#4a90e2")
        
        # Update course list
        self.group_courses_listbox.delete(0, "end")
        for course_code in group.courses:
            # Find title for this course
            title = ""
            for section in self.sections:
                if section.course == course_code:
                    title = get_course_title(section)
                    break
            
            if title:
                display_text = f"{course_code} ({truncate_text(title, 25)})"
            else:
                display_text = course_code
            self.group_courses_listbox.insert("end", display_text)
        
        # Update status
        course_count = len(group.courses)
        if course_count == 0:
            self.course_op_status.config(text="No courses in this group yet. Select courses from the table and click 'Add Selected Courses'", 
                                       foreground="orange")
        else:
            self.course_op_status.config(text=f"{course_count} courses in group. Select courses above to remove them.", 
                                       foreground="green")
        
        # Enable remove button
        self.remove_btn.config(state="normal" if course_count > 0 else "disabled")
    
    def _add_to_group(self):
        # Use stored group index instead of relying on current selection
        if self.current_selected_group_index is None:
            messagebox.showwarning("Select Group", "Please select a group first from the list on the left.")
            return
        
        group = self.course_groups[self.current_selected_group_index]
        
        tree_sel = self.tree.selection()
        if not tree_sel:
            messagebox.showinfo("Select Courses", "Please select one or more courses from the main table to add to the group.")
            return
        
        added = 0
        skipped_required = 0
        skipped_duplicate = 0
        
        for iid in tree_sel:
            s = self.sections[int(iid)]
            if s.course in self.required_courses:
                skipped_required += 1
            elif s.course in group.courses:
                skipped_duplicate += 1
            else:
                group.courses.append(s.course)
                added += 1
        
        # Provide detailed feedback
        messages = []
        if added > 0:
            messages.append(f"✅ Added {added} course(s) to '{group.name}'")
        if skipped_required > 0:
            messages.append(f"⚠️ Skipped {skipped_required} course(s) that are already required")
        if skipped_duplicate > 0:
            messages.append(f"ℹ️ Skipped {skipped_duplicate} course(s) already in the group")
        
        if messages:
            messagebox.showinfo("Group Update", "\n".join(messages))
        
        if added > 0:
            # Refresh displays
            self._refresh_groups_listbox()
            self.groups_listbox.selection_set(self.current_selected_group_index)
            self._on_group_select(None)
            
            # Update faculty preferences dropdown to include new courses
            self._update_course_combo()
            
            # Update status
            self.status_label.config(text=f"✅ Added {added} course(s) to group", foreground="green")
            self.root.after(3000, lambda: self.status_label.config(text="Ready to configure schedule", foreground="blue"))
    
    def _remove_from_group_enhanced(self):
        """Enhanced remove method with better UX"""
        if self.current_selected_group_index is None:
            messagebox.showwarning("Select Group", "Please select a group first.")
            return
        
        group = self.course_groups[self.current_selected_group_index]
        course_selections = self.group_courses_listbox.curselection()
        
        if not course_selections:
            messagebox.showinfo("Select Courses", 
                              f"Please select courses to remove from '{group.name}'.\n\n" + 
                              "Tip: You can select multiple courses by holding Ctrl while clicking.")
            return
        
        # Get selected course names
        courses_to_remove = []
        course_codes_to_remove = []
        for idx in course_selections:
            display_text = self.group_courses_listbox.get(idx)
            courses_to_remove.append(display_text)
            
            # Extract course code from display text (format: "CODE (Title)")
            if " (" in display_text:
                course_code = display_text.split(" (")[0]
            else:
                course_code = display_text
            course_codes_to_remove.append(course_code)
        
        # Confirm removal
        if len(courses_to_remove) == 1:
            message = f"Remove '{courses_to_remove[0]}' from group '{group.name}'?"
        else:
            course_list = "', '".join(courses_to_remove)
            message = f"Remove {len(courses_to_remove)} courses from group '{group.name}'?\n\nCourses to remove: '{course_list}'"
        
        if not messagebox.askyesno("Confirm Removal", message):
            return
        
        # Remove courses using the extracted course codes
        for course_code in course_codes_to_remove:
            if course_code in group.courses:
                group.courses.remove(course_code)
        
        # Refresh displays
        self._refresh_groups_listbox()
        self.groups_listbox.selection_set(self.current_selected_group_index)
        self._on_group_select(None)
        
        # Update faculty preferences dropdown to reflect removed courses
        self._update_course_combo()
        
        # Success feedback
        if len(courses_to_remove) == 1:
            self.status_label.config(text=f"✅ Removed '{courses_to_remove[0]}' from group", foreground="green")
        else:
            self.status_label.config(text=f"✅ Removed {len(courses_to_remove)} courses from group", foreground="green")
        self.root.after(3000, lambda: self.status_label.config(text="Ready to configure schedule", foreground="blue"))

    def _on_group_course_select(self, event):
        """Handle selection of courses within a group"""
        if self.current_selected_group_index is None:
            return
            
        selections = self.group_courses_listbox.curselection()
        if selections:
            count = len(selections)
            if count == 1:
                course = self.group_courses_listbox.get(selections[0])
                self.course_op_status.config(text=f"Selected: '{course}'. Click 'Remove Selected' to remove it.", 
                                           foreground="#ff6b6b")
            else:
                self.course_op_status.config(text=f"Selected {count} courses. Click 'Remove Selected' to remove them.", 
                                           foreground="#ff6b6b")
            self.remove_btn.config(state="normal")
        else:
            group = self.course_groups[self.current_selected_group_index]
            course_count = len(group.courses)
            if course_count > 0:
                self.course_op_status.config(text=f"{course_count} courses in group. Select courses above to remove them.", 
                                           foreground="green")
            self.remove_btn.config(state="disabled")

    def _clear_group_courses(self):
        """Clear all courses from the selected group"""
        if self.current_selected_group_index is None:
            messagebox.showwarning("Select Group", "Please select a group first.")
            return
            
        group = self.course_groups[self.current_selected_group_index]
        if not group.courses:
            messagebox.showinfo("Empty Group", f"Group '{group.name}' has no courses to clear.")
            return
            
        if messagebox.askyesno("Clear All Courses", 
                             f"Remove ALL {len(group.courses)} courses from group '{group.name}'?\n\n" +
                             "This action cannot be undone."):
            group.courses.clear()
            self._refresh_groups_listbox()
            self.groups_listbox.selection_set(self.current_selected_group_index)
            self._on_group_select(None)
            
            # Update faculty preferences dropdown to reflect cleared courses
            self._update_course_combo()
            
            self.status_label.config(text=f"✅ Cleared all courses from '{group.name}'", foreground="green")
            self.root.after(3000, lambda: self.status_label.config(text="Ready to configure schedule", foreground="blue"))

    def _select_all_group_courses(self):
        """Select all courses in the group listbox"""
        if self.current_selected_group_index is None:
            return
            
        count = self.group_courses_listbox.size()
        if count > 0:
            self.group_courses_listbox.selection_set(0, count-1)
            self.course_op_status.config(text=f"Selected all {count} courses. Click 'Remove Selected' to remove them.", 
                                       foreground="#ff6b6b")
            self.remove_btn.config(state="normal")

    # ---------- data loading ----------
    def _open_csv(self):
        path = filedialog.askopenfilename(title="Open CSV file", filetypes=[("CSV files","*.csv"),("All files","*.*")])
        if not path:
            return
        try:
            with open(path, newline='', encoding='utf-8') as f:
                text = f.read()
            self._load_from_csv_text(text)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {e}")

    def _paste_clipboard(self):
        try:
            txt = self.root.clipboard_get()
        except Exception:
            messagebox.showerror("Clipboard", "No text found in clipboard.")
            return
        if not txt.strip():
            messagebox.showerror("Clipboard", "Clipboard text is empty.")
            return
        self._load_from_csv_text(txt)

    def _load_from_csv_text(self, text: str):
        try:
            f = io.StringIO(text)
            reader = csv.DictReader(f)
            rows = [r for r in reader]
            if not rows:
                messagebox.showerror("CSV", "No rows parsed. Ensure header row exists.")
                return
            self._load_from_rows(rows)
        except Exception as e:
            messagebox.showerror("CSV parse error", str(e))

    def _load_from_rows(self, rows: List[Dict]):
        self.sections = []
        for r in rows:
            course = (r.get("Course #") or r.get("Course") or "").strip()
            sec = (r.get("Sec") or "").strip()
            faculty = (r.get("Faculty") or "").strip()
            days = parse_days(r.get("Days","") or r.get("Day",""))
            start = parse_time(r.get("Start Time") or r.get("Start") or "")
            end = parse_time(r.get("End Time") or r.get("End") or "")
            cr = r.get("CR") or r.get("Credits") or r.get("Credit") or "0"
            try:
                credits = float(cr)
            except Exception:
                credits = 0.0
            s = Section(course, sec, faculty, days, start, end, credits, r)
            if(course):
                self.sections.append(s)  
        self._refresh_table()
        self._update_data_status()
        messagebox.showinfo("Success", f"✅ Loaded {len(self.sections)} sections successfully!")
 
    def _clear_table(self):
        self.sections = []
        self._refresh_table()
        self._update_data_status()
    def _refresh_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        filt = self.filter_var.get().strip().lower()
        for idx, s in enumerate(self.sections):
            title = s.raw.get("Course Title","")
            remark = s.raw.get("Remarks","") or s.raw.get("Remark","") or ""
            if filt:
                low_course = (s.course or "").lower()
                low_fac = (s.faculty or "").lower()
                low_title = (title or "").lower()
                low_remark = (remark or "").lower()
                if filt not in low_course and filt not in low_fac and filt not in low_title and filt not in low_remark:
                    continue
            self.tree.insert("", "end", iid=str(idx), values=(
                s.course, s.sec, title, str(int(s.credits)) if s.credits else "", s.faculty, "".join(s.days),
                minutes_to_str(s.start), minutes_to_str(s.end), s.raw.get("Room",""), s.raw.get("Remarks","")
            ))

    # ---------- interactions ----------
    def _on_tree_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        s = self.sections[idx]
        if s.course not in self.required_courses:
            self.required_courses.append(s.course)
            # Format course display with title
            title = get_course_title(s)
            if title:
                display_text = f"{s.course} ({truncate_text(title, 30)})"
            else:
                display_text = s.course
            self.req_listbox.insert("end", display_text)
            self._update_req_status()
            self._update_course_combo()

    def _add_selected_required(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select Courses", "Please select one or more courses from the table first.")
            return
        added = 0
        for iid in sel:
            s = self.sections[int(iid)]
            if s.course not in self.required_courses:
                self.required_courses.append(s.course)
                # Format course display with title
                title = get_course_title(s)
                if title:
                    display_text = f"{s.course} ({truncate_text(title, 30)})"
                else:
                    display_text = s.course
                self.req_listbox.insert("end", display_text)
                added += 1
        if added == 0:
            messagebox.showinfo("Already Added", "Selected courses are already in the required list.")
        else:
            self.status_label.config(text=f"✅ Added {added} required course(s)", foreground="green")
            self.root.after(2000, lambda: self.status_label.config(text="Ready to configure schedule", foreground="blue"))
        self._update_req_status()
        self._update_course_combo()

    def _remove_selected_required(self):
        sel = self.req_listbox.curselection()
        if not sel:
            messagebox.showinfo("Select Course", "Please select a course to remove from the required list.")
            return
        idx = sel[0]
        display_text = self.req_listbox.get(idx)
        
        # Extract course code from display text (format: "CODE (Title)")
        if " (" in display_text:
            course_code = display_text.split(" (")[0]
        else:
            course_code = display_text
        
        self.req_listbox.delete(idx)
        if course_code in self.required_courses:
            self.required_courses.remove(course_code)
        self._update_req_status()
        self._update_course_combo()

    def _clear_required(self):
        if self.required_courses and not messagebox.askyesno("Confirm", "Clear all required courses and faculty preferences?"):
            return
        self.required_courses.clear()
        self.req_listbox.delete(0, "end")
        self.faculty_prefs.clear()
        self._update_req_status()
        self._update_course_combo()
        self.status_label.config(text="Required courses cleared", foreground="blue")

    def _on_faculty_click(self, event):
        """Handle faculty combo click - ensure course stays selected"""
        # Just make sure we maintain the selected course info
        if self.current_selected_course:
            self.selected_course_label.config(text=f"Selected: {self.current_selected_course}", foreground="blue")

    def _on_faculty_selected(self, event):
        """Handle faculty selection"""
        # Keep the course selection visible
        if self.current_selected_course:
            self.selected_course_label.config(text=f"Selected: {self.current_selected_course}", foreground="blue")

    def _on_course_click(self, event):
        """Handle click on course in group - maintain group context"""
        # This method is kept for compatibility but the new selection handling is in _on_group_course_select
        pass

    def _update_course_combo(self):
        """Update the course combobox with courses that have multiple faculty options"""
        if hasattr(self, 'course_combo'):
            current = self.course_combo.get()
            
            # Collect all courses: required + all courses in groups
            all_courses = set(self.required_courses)
            for group in self.course_groups:
                all_courses.update(group.courses)
            
            # Create a mapping from course code to sections for getting titles
            course_sections = {}
            for section in self.sections:
                if section.course in all_courses:
                    if section.course not in course_sections:
                        course_sections[section.course] = []
                    course_sections[section.course].append(section)
            
            # Filter courses to only include those with multiple faculty options
            courses_with_multiple_faculty = []
            for course in sorted(all_courses):
                if course in course_sections:
                    # Get unique faculty members for this course
                    faculties = {s.faculty for s in course_sections[course] if s.faculty.strip()}
                    if len(faculties) > 1:  # Only include courses with multiple faculty
                        courses_with_multiple_faculty.append(course)
            
            # Format courses with titles
            course_display_list = []
            course_mapping = {}  # Map display text to course code
            
            for course in courses_with_multiple_faculty:
                if course in course_sections:
                    display_text = format_course_display(course, course_sections[course], 60)
                    course_display_list.append(display_text)
                    course_mapping[display_text] = course
            
            self.course_combo['values'] = course_display_list
            self.course_display_mapping = course_mapping  # Store mapping for later use
            
            # Update the label to show how many courses are available for preferences
            total_courses = len(all_courses)
            available_courses = len(course_display_list)
            
            if hasattr(self, 'pref_status_label'):
                if available_courses == 0:
                    if total_courses > 0:
                        self.pref_status_label.config(text="No courses with multiple faculty options", foreground="orange")
                    else:
                        self.pref_status_label.config(text="Add required courses or groups first", foreground="gray")
                else:
                    self.pref_status_label.config(text=f"{available_courses} of {total_courses} courses have faculty options", foreground="blue")
            
            # Try to preserve selection if it's still valid
            current_display = None
            for display, code in course_mapping.items():
                if code == current or display == current:
                    current_display = display
                    break
            
            if current_display:
                self.course_combo.set(current_display)
            else:
                self.course_combo.set("")
            self._update_prefs_display()

    def _on_course_combo_select(self, event):
        """Handle course selection from combo"""
        display_text = self.course_combo.get()
        if not display_text:
            self.faculty_combo['values'] = []
            self.faculty_combo.set("")
            self.pref_status_label.config(text="Select a course first", foreground="gray")
            return
        
        # Get the actual course code from the display mapping
        course = getattr(self, 'course_display_mapping', {}).get(display_text, display_text)
        if not course:
            return
            
        # Update faculty options for selected course
        faculties = sorted({s.faculty for s in self.sections if s.course == course and s.faculty.strip()})
        
        if len(faculties) <= 1:
            # This shouldn't happen since we filter in _update_course_combo, but just in case
            self.faculty_combo['values'] = []
            self.faculty_combo.set("")
            self.pref_status_label.config(text=f"{course} has only one faculty option", foreground="orange")
            return
        
        # Set up faculty options
        self.faculty_combo['values'] = ["No preference"] + faculties
        
        # Set current preference if exists
        pref = self.faculty_prefs.get(course, "No preference")
        if pref not in self.faculty_combo['values']:
            pref = "No preference"
        self.faculty_combo.set(pref)
        
        # Show helpful status message
        faculty_list = "', '".join(faculties)
        self.pref_status_label.config(text=f"Faculty options: '{faculty_list}'", foreground="blue")

    def _set_fac_pref_new(self):
        """Set faculty preference using independent dropdowns"""
        display_text = self.course_combo.get()
        if not display_text:
            messagebox.showinfo("Select Course", "Please select a course from the dropdown.")
            return
        
        # Get the actual course code from the display mapping
        course = getattr(self, 'course_display_mapping', {}).get(display_text, display_text)
        if not course:
            return
            
        val = self.faculty_combo.get()
        if not val:
            messagebox.showinfo("Select Faculty", "Please select a faculty preference.")
            return
        
        if val == "No preference":
            if course in self.faculty_prefs:
                del self.faculty_prefs[course]
        else:
            self.faculty_prefs[course] = val
        
        # Show the course code in the status message for clarity
        course_display = course
        if hasattr(self, 'course_display_mapping'):
            # Find the display text for this course
            for display, code in self.course_display_mapping.items():
                if code == course:
                    course_display = display
                    break
        
        self.pref_status_label.config(text=f"✅ Preference set for {course_display}", foreground="green")
        self.root.after(2000, lambda: self.pref_status_label.config(text="Select another course or continue", foreground="blue"))
        self._update_prefs_display()

    def _update_prefs_display(self):
        """Update the display of current faculty preferences"""
        if not hasattr(self, 'prefs_display'):
            return
            
        self.prefs_display.config(state="normal")
        self.prefs_display.delete(1.0, 'end')
        
        if self.faculty_prefs:
            self.prefs_display.insert(1.0, "Current faculty preferences:\n")
            for course, faculty in self.faculty_prefs.items():
                # Find course title
                title = ""
                for section in self.sections:
                    if section.course == course:
                        title = get_course_title(section)
                        break
                
                if title:
                    course_display = f"{course} ({truncate_text(title, 25)})"
                else:
                    course_display = course
                    
                self.prefs_display.insert('end', f"• {course_display}: {faculty}\n")
        else:
            self.prefs_display.insert(1.0, "No faculty preferences set yet")
        
        self.prefs_display.config(state="disabled")

    def _make_tree_context_menu(self):
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Lock this section (force into schedule)", command=self._lock_selected_section)
        self.menu.add_command(label="Unlock this section (if locked)", command=self._unlock_selected_section)
        self.tree.bind("<Button-3>", self._show_tree_menu)

    def _show_tree_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    def _lock_selected_section(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        s = self.sections[idx]
        if any(ls.course == s.course and ls.sec == s.sec for ls in self.locked_sections):
            messagebox.showinfo("Locked", "This section is already locked.")
            return
        self.locked_sections.append(s)
        self.lock_listbox.insert("end", f"{s.course} Sec {s.sec} | {s.faculty} | {''.join(s.days)} {minutes_to_str(s.start)}")
        if s.course not in self.required_courses:
            self.required_courses.append(s.course)
            # Format course display with title
            title = get_course_title(s)
            if title:
                display_text = f"{s.course} ({truncate_text(title, 30)})"
            else:
                display_text = s.course
            self.req_listbox.insert("end", display_text)

    def _unlock_selected_section(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        s = self.sections[idx]
        for i, ls in enumerate(self.locked_sections):
            if ls.course == s.course and ls.sec == s.sec:
                self.locked_sections.pop(i)
                self.lock_listbox.delete(i)
                messagebox.showinfo("Unlocked", f"Unlocked {s.course} Sec {s.sec}")
                return
        messagebox.showinfo("Not locked", "This section was not locked.")

    def _remove_selected_lock(self):
        sel = self.lock_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.lock_listbox.delete(idx)
        self.locked_sections.pop(idx)

    # ---------- scheduling ----------
    def _run_scheduler_threaded(self):
        # Validation with better messages
        if not self.required_courses and not self.locked_sections and not self.course_groups:
            messagebox.showwarning("No Courses Selected", 
                                 "Please select required courses, create course groups, or lock sections first.\n\n" +
                                 "Use the steps above to configure your schedule preferences.")
            return
            
        try:
            min_c = float(self.min_spin.get())
            max_c = float(self.max_spin.get())
            if min_c > max_c:
                messagebox.showerror("Invalid Credit Range", "Minimum credits cannot be greater than maximum credits.")
                return
            if min_c < 0 or max_c < 0:
                messagebox.showerror("Invalid Credits", "Credit values cannot be negative.")
                return
        except Exception:
            messagebox.showerror("Invalid Credits", "Please enter valid numeric values for credits.")
            return
        
        # Show progress with better feedback
        self._set_ui_state("disabled")
        self.progress.start(10)
        self.progress_label.config(text="🔍 Analyzing course combinations...")
        self.status_label.config(text="Generating schedule...", foreground="orange")
        
        visualizer = None
        if self.visualize_var.get():
            visualizer = Visualizer(self.root)
        
        # Store visualizer for later use
        self.current_visualizer = visualizer
            
        t = threading.Thread(target=self._scheduler_worker, args=(min_c, max_c, visualizer), daemon=True)
        t.start()

    def _scheduler_worker(self, min_c, max_c, visualizer=None):
        try:
            def viz_callback(action, course, section, score, current_schedule):
                if visualizer:
                    # Make a copy of schedule to avoid thread safety issues during drawing
                    schedule_copy = current_schedule.copy()
                    visualizer.window.after(0, visualizer.update_schedule, 
                                          schedule_copy, action, course, score)
                    # Longer pause for best solutions to make them more visible
                    delay = visualizer.delay_var.get()
                    if action == "best":
                        delay = max(delay * 3, 1.0)  # At least 1 second for best solutions
                    time.sleep(delay)

            best = find_best_schedule(
                self.sections,
                self.required_courses,
                self.course_groups,
                self.faculty_prefs,
                self.day_time_prefs,
                self.locked_sections,
                min_c,
                max_c,
                callback=viz_callback if visualizer else None
            )
            self.result_queue.put(("ok", best))
        except Exception as e:
            self.result_queue.put(("err", str(e)))

    def _poll_result_queue(self):
        try:
            item = self.result_queue.get_nowait()
        except queue.Empty:
            self.root.after(200, self._poll_result_queue)
            return
        
        self.progress.stop()
        self.progress_label.config(text="")
        self._set_ui_state("normal")
        
        status, payload = item
        if status == "err":
            self.status_label.config(text="❌ Scheduling failed", foreground="red")
            self.result_status_label.config(text="❌ Error occurred during scheduling", foreground="red")
            messagebox.showerror("Scheduling Error", 
                               f"Failed to generate schedule:\n\n{payload}\n\n" +
                               "Try adjusting your requirements or credit range.")
        else:
            best = payload
            self._display_results(best)
        
        self.root.after(200, self._poll_result_queue)

    def _set_ui_state(self, state: str):
        for w in (self.tree, self.req_listbox, self.groups_listbox, self.lock_listbox, self.faculty_combo):
            try:
                w.configure(state=state)
            except Exception:
                pass

    def _display_results(self, best):
        for i in self.res_tree.get_children():
            self.res_tree.delete(i)
            
        if not best["schedule"]:
            self.result_status_label.config(text="❌ No feasible schedule found", foreground="red")
            self.status_label.config(text="No schedule found - try adjusting requirements", foreground="red")
            messagebox.showinfo("No Schedule Found", 
                               "No feasible schedule found with current constraints.\n\n" +
                               "Try:\n" +
                               "• Reducing required courses\n" +
                               "• Increasing maximum credits\n" +
                               "• Removing some course groups\n" +
                               "• Unlocking some sections")
            return
            
        schedule = best["schedule"]
        score = best["score"]
        total_credits = best.get("credits", 0.0)
        
        # Display schedule
        for s in schedule:
            sc = score_section(s, self.faculty_prefs, self.day_time_prefs)
            title = truncate_text(get_course_title(s), 35)  # Truncate title if too long
            self.res_tree.insert("", "end", values=(
                s.course, title, s.sec, s.faculty, "".join(s.days), 
                minutes_to_str(s.start), minutes_to_str(s.end), 
                s.raw.get("Room",""), f"{s.credits:.1f}", f"{sc:.1f}"
            ))
        
        # Update status
        self.result_status_label.config(text=f"✅ Generated schedule: {len(schedule)} courses, {total_credits:.1f} credits, score {score:.1f}", foreground="green")
        self.status_label.config(text="✅ Schedule generated successfully!", foreground="green")
        
        # Final visualization update to show the complete best solution
        if hasattr(self, 'current_visualizer') and self.current_visualizer:
            try:
                self.current_visualizer.update_schedule(schedule, "FINAL", "COMPLETE SOLUTION", score)
            except Exception as e:
                print(f"Visualization update error: {e}")
        
        # Success message with details
        course_list = ", ".join(s.course for s in schedule)
        messagebox.showinfo("Success!", 
                          f"✅ Schedule generated successfully!\n\n" +
                          f"📚 Courses: {len(schedule)} courses ({course_list})\n" +
                          f"📊 Credits: {total_credits:.1f}\n" +
                          f"⭐ Score: {score:.1f}\n\n" +
                          f"Your schedule is displayed below. You can export it to CSV if needed.")
        
        # Auto-expand results panel
        try:
            w = self.root.winfo_width() or 1200
            new_x = int(w * 0.55)  # Show more of the results
            self.paned.sash_place(0, new_x, 0)
        except Exception:
            pass
        
        # Focus on results
        children = self.res_tree.get_children()
        if children:
            self.res_tree.focus(children[0])
            self.res_tree.selection_set(children[0])
            self.res_tree.see(children[0])
            self.res_tree.focus_set()

    def _export_schedule(self):
        rows = []
        for iid in self.res_tree.get_children():
            vals = self.res_tree.item(iid, "values")
            rows.append(vals)
        if not rows:
            messagebox.showinfo("No results", "No schedule to export.")
            return
        path = filedialog.asksaveasfilename(title="Save schedule CSV", defaultextension=".csv", filetypes=[("CSV files","*.csv")])
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                # Updated header to include Title column
                writer.writerow(["Course","Title","Sec","Faculty","Days","Start","End","Room","Credits","Score"])
                for r in rows:
                    writer.writerow(r)
            messagebox.showinfo("Saved", f"Schedule exported to {path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def _open_results_window(self):
        win = tk.Toplevel(self.root)
        win.title("Schedule Results")
        win.geometry("900x400")
        cols = ("Course","Title","Sec","Faculty","Days","Start","End","Room","Credits","Score")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=90, anchor="w")
        tree.column("Title", width=180)
        tree.column("Faculty", width=160)
        tree.pack(fill="both", expand=True)
        for iid in self.res_tree.get_children():
            vals = self.res_tree.item(iid, "values")
            tree.insert("", "end", values=vals)
        ttk.Button(win, text="Close", command=win.destroy).pack(pady=6)

if __name__ == "__main__":
    root = tk.Tk()
    app = SchedulerGUI(root)
    root.mainloop()