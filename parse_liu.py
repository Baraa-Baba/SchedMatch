from bs4 import BeautifulSoup
from convertliu import coursesHtml
import csv
from datetime import datetime
import re

OUTPUT_CSV = "course_fall2026_liu.csv"


def fmt_time_24_to_ampm(t24):
    """Convert H:M (24h) to format like '8:00:00 AM'"""
    try:
        dt = datetime.strptime(t24.strip(), "%H:%M")
        return dt.strftime("%-I:%M:%S %p")
    except Exception:
        return ""


def normalize_days(token):
    # Normalize tokens: turn 'TTh' or 'Th' into 'R' (Thursday symbol used in CSV),
    # then separate letters with spaces: e.g., 'MW' -> 'M W', 'TR' -> 'T R'
    t = token.replace("TTh", "TR").replace("Th", "R").replace("tth", "tr").replace("th", "r")
    # Remove any non-letter characters
    t = re.sub(r"[^A-Za-z]", "", t)
    return " ".join(list(t))


def extract_course_code(text):
    # Try to find code like ABC123 or ABC123A
    m = re.search(r"[A-Z]{2,}[0-9A-Z\-]{2,}", text)
    if m:
        return m.group(0).strip()
    # fallback: first token
    return text.split()[0].strip() if text else ""


def parse_rows(html, campus_filter="Beirut"):
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("table#myClassesTable tbody tr")
    out = []
    for tr in rows:
        tds = tr.find_all("td")
        if len(tds) < 7:
            continue

        # Many pages include a small index in tds[1]
        seq = tds[1].get_text(strip=True)

        code_text = tds[2].get_text(" ", strip=True)
        course_code = extract_course_code(code_text)

        title = tds[3].get_text(strip=True)

        credits = tds[4].get_text(strip=True)

        section = tds[5].get_text(strip=True)

        schedule = tds[6].get_text(" ", strip=True)
        days = ""
        start_time = ""
        end_time = ""
        if schedule:
            parts = schedule.split()
            if len(parts) >= 2:
                days_token = parts[0]
                time_range = parts[1]
                days = normalize_days(days_token)
                if "-" in time_range:
                    start, end = time_range.split("-", 1)
                    start_time = fmt_time_24_to_ampm(start)
                    end_time = fmt_time_24_to_ampm(end)
            else:
                # sometimes schedule may be just times or other form
                m = re.search(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", schedule)
                if m:
                    start_time = fmt_time_24_to_ampm(m.group(1))
                    end_time = fmt_time_24_to_ampm(m.group(2))

        # campus is typically in td index 8
        campus = ""
        if len(tds) >= 9:
            campus = tds[8].get_text(strip=True)

        instructor = ""
        if len(tds) >= 10:
            instructor = tds[9].get_text(strip=True)

        if campus_filter and campus.strip().lower() != campus_filter.strip().lower():
            continue

        remarks = "LIU Fall 2026"
        if campus:
            remarks = f"LIU Fall 2026, Campus: {campus}"

        row = [
            course_code,
            seq,
            title,
            credits,
            instructor,
            days,
            start_time,
            end_time,
            "",
            remarks,
        ]
        out.append(row)
    return out


def write_csv(rows, path=OUTPUT_CSV):
    header = [
        "Course #",
        "Sec",
        "Course Title",
        "CR",
        "Faculty",
        "Days",
        "Start Time",
        "End Time",
        "Room",
        "Remarks",
    ]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def main():
    rows = parse_rows(coursesHtml, campus_filter="Beirut")
    write_csv(rows)
    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
