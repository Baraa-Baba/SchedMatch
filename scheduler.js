/**
 * Course Scheduler - Core Algorithm
 * Ported from Python tkinter application
 */

const DAY_CHARS = new Set(['M', 'T', 'W', 'R', 'F', 'S']);

/**
 * Parse time string to minutes since midnight
 * @param {string} timeStr - Time string (e.g., "2:30 PM", "14:30")
 * @returns {number|null} - Minutes since midnight or null
 */
function parseTime(timeStr) {
    if (!timeStr || timeStr.trim() === '') return null;

    timeStr = timeStr.trim();

    // Try different time formats
    const formats = [
        // 12-hour format with AM/PM
        /(\d{1,2}):(\d{2}):(\d{2})\s*(AM|PM)/i,
        /(\d{1,2}):(\d{2})\s*(AM|PM)/i,
        /(\d{1,2})\s*(AM|PM)/i,
        // 24-hour format
        /(\d{1,2}):(\d{2}):(\d{2})/,
        /(\d{1,2}):(\d{2})/
    ];

    for (const format of formats) {
        const match = timeStr.match(format);
        if (match) {
            let hours = parseInt(match[1]);
            const minutes = match[2] ? parseInt(match[2]) : 0;
            const ampm = match[3] || match[4];

            if (ampm) {
                if (ampm.toUpperCase() === 'PM' && hours !== 12) {
                    hours += 12;
                } else if (ampm.toUpperCase() === 'AM' && hours === 12) {
                    hours = 0;
                }
            }

            return hours * 60 + minutes;
        }
    }

    return null;
}

/**
 * Parse days string into array of day characters
 * @param {string} daysStr - Days string (e.g., "MWF", "TR")
 * @returns {string[]} - Array of day characters
 */
function parseDays(daysStr) {
    if (!daysStr) return [];
    return Array.from(daysStr.trim()).filter(c => DAY_CHARS.has(c));
}

/**
 * Convert minutes to time string
 * @param {number|null} minutes - Minutes since midnight
 * @returns {string} - Formatted time string
 */
function minutesToStr(minutes) {
    if (minutes === null || minutes === undefined) return '';

    const hour = Math.floor(minutes / 60);
    const minute = minutes % 60;
    const ampm = hour < 12 ? 'AM' : 'PM';
    let displayHour = hour % 12;
    if (displayHour === 0) displayHour = 12;

    return `${displayHour}:${minute.toString().padStart(2, '0')} ${ampm}`;
}

/**
 * Section class representing a course section
 */
class Section {
    constructor(course, sec, faculty, days, start, end, credits, raw) {
        this.course = course;
        this.sec = sec;
        this.faculty = faculty;
        this.days = days;
        this.start = start;
        this.end = end;
        this.credits = credits;
        this.raw = raw;
    }
}

/**
 * CourseGroup class for managing course groups
 */
class CourseGroup {
    constructor(name, courses, numRequired) {
        this.name = name;
        this.courses = courses || [];
        this.numRequired = numRequired;
    }
}

/**
 * Check if two sections overlap in time
 * @param {Section} a - First section
 * @param {Section} b - Second section
 * @returns {boolean} - True if sections overlap
 */
function overlaps(a, b) {
    if (!a.days || !b.days || a.start === null || b.start === null) {
        return false;
    }

    // Check if they share any days
    const sharedDays = a.days.some(day => b.days.includes(day));
    if (!sharedDays) return false;

    // Check if times overlap
    return (a.start < b.end) && (b.start < a.end);
}

/**
 * Check if a section meets all time requirements (hard constraints)
 * @param {Section} section - Section to check
 * @param {Object} dayTimePrefs - Day-specific time preferences
 * @returns {boolean} - True if section meets all requirements
 */
function checkTimeRequirements(section, dayTimePrefs) {
    if (!section.days || section.start === null) {
        return true; // No time data, can't enforce requirements
    }

    for (const day of section.days) {
        if (dayTimePrefs[day] && dayTimePrefs[day].enabled && dayTimePrefs[day].isRequirement) {
            const dayPref = dayTimePrefs[day];
            const reqStart = parseTime(dayPref.startTime);
            const reqEnd = parseTime(dayPref.endTime);

            if (reqStart !== null && reqEnd !== null) {
                const sectionStart = section.start;
                const sectionEnd = section.end || (section.start + 60); // Assume 1 hour if no end time

                // Check if section is within required time range
                if (!(sectionStart >= reqStart && sectionEnd <= reqEnd)) {
                    return false; // Violates time requirement
                }
            }
        }
    }

    return true; // All requirements satisfied
}

/**
 * Score a section based on preferences
 * @param {Section} section - Section to score
 * @param {Object} facultyPrefs - Faculty preferences by course
 * @param {Object} dayTimePrefs - Day-specific time preferences
 * @returns {number} - Score for the section
 */
function scoreSection(section, facultyPrefs, dayTimePrefs) {
    let score = 0.0;

    // Faculty preference scoring
    const pref = facultyPrefs[section.course];
    if (pref && pref.trim().toLowerCase() === section.faculty.trim().toLowerCase()) {
        score += 100.0;
    }

    // Time preference scoring
    if (section.start !== null && section.days) {
        for (const day of section.days) {
            if (dayTimePrefs[day] && dayTimePrefs[day].enabled) {
                const dayPref = dayTimePrefs[day];
                const prefStart = parseTime(dayPref.startTime);
                const prefEnd = parseTime(dayPref.endTime);

                if (prefStart !== null && prefEnd !== null) {
                    const sectionStart = section.start;
                    const sectionEnd = section.end || (section.start + 60);

                    // Calculate overlap
                    const overlapStart = Math.max(sectionStart, prefStart);
                    const overlapEnd = Math.min(sectionEnd, prefEnd);

                    if (overlapStart < overlapEnd) {
                        // There is overlap
                        const overlapDuration = overlapEnd - overlapStart;
                        const sectionDuration = sectionEnd - sectionStart;
                        const overlapRatio = sectionDuration > 0 ? overlapDuration / sectionDuration : 0;

                        if (dayPref.isRequirement) {
                            // For requirements, give high bonus for full compliance
                            if (overlapRatio >= 0.95) {
                                score += 50.0;
                            } else {
                                score += 25.0 * overlapRatio;
                            }
                        } else {
                            // For preferences, give proportional bonus
                            score += 30.0 * overlapRatio;
                        }
                    } else {
                        // No overlap - penalty for requirements
                        if (dayPref.isRequirement) {
                            score -= 200.0; // Heavy penalty
                        }
                    }
                }
            }
        }
    }

    return score;
}

/**
 * Calculate gap penalty for a schedule
 * @param {Section[]} chosen - Array of chosen sections
 * @returns {number} - Penalty score
 */
function gapPenalty(chosen) {
    let penalty = 0.0;
    const byDay = {};

    for (const section of chosen) {
        if (section.start === null) continue;
        for (const day of section.days) {
            if (!byDay[day]) byDay[day] = [];
            byDay[day].push([section.start, section.end]);
        }
    }

    for (const intervals of Object.values(byDay)) {
        intervals.sort((a, b) => a[0] - b[0]);
        for (let i = 0; i < intervals.length - 1; i++) {
            const gap = intervals[i + 1][0] - intervals[i][1];
            if (gap > 0) {
                penalty += gap * 0.2;
            }
        }
    }

    return penalty;
}

/**
 * Find the best schedule using backtracking algorithm
 * @param {Section[]} sections - All available sections
 * @param {string[]} requiredCourses - Required courses
 * @param {CourseGroup[]} courseGroups - Course groups
 * @param {Object} facultyPrefs - Faculty preferences
 * @param {Object} dayTimePrefs - Time preferences by day
 * @param {Section[]} lockedSections - Locked sections
 * @param {number} minCredits - Minimum credits
 * @param {number} maxCredits - Maximum credits
 * @param {Function} callback - Callback for progress updates
 * @returns {Object} - Best schedule with score and credits
 */
function findBestSchedule(
    sections,
    requiredCourses,
    courseGroups,
    facultyPrefs,
    dayTimePrefs,
    lockedSections,
    minCredits,
    maxCredits,
    callback = null
) {
    // Group sections by course
    const byCourse = {};
    for (const s of sections) {
        if (!byCourse[s.course]) byCourse[s.course] = [];
        byCourse[s.course].push(s);
    }

    // Include locked sections in required courses
    const reqSet = new Set(requiredCourses);
    for (const ls of lockedSections) {
        reqSet.add(ls.course);
    }
    const updatedRequired = Array.from(reqSet);

    // Restrict locked courses to the locked section only
    for (const ls of lockedSections) {
        if (byCourse[ls.course]) {
            byCourse[ls.course] = byCourse[ls.course].filter(
                s => s.sec === ls.sec && s.faculty === ls.faculty
            );
        }
    }

    // Pre-filter sections by hard time requirements
    const filteredSections = {};
    for (const [course, secs] of Object.entries(byCourse)) {
        filteredSections[course] = secs.filter(s => checkTimeRequirements(s, dayTimePrefs));
    }

    // Build group constraints
    const groupConstraints = {};
    const allCourses = [...updatedRequired];

    for (const group of courseGroups) {
        const validCourses = group.courses.filter(
            c => !updatedRequired.includes(c) && filteredSections[c] && filteredSections[c].length > 0
        );
        if (validCourses.length > 0) {
            groupConstraints[group.name] = {
                courses: validCourses,
                numRequired: Math.min(group.numRequired, validCourses.length)
            };
            allCourses.push(...validCourses);
        }
    }

    // Order courses by number of options (fewest first)
    const uniqueCourses = [...new Set(allCourses)];
    const orderedCourses = uniqueCourses.sort(
        (a, b) => (filteredSections[a] || []).length - (filteredSections[b] || []).length
    );

    // Map course to type (required/group)
    const courseInfo = {};
    for (const c of orderedCourses) {
        if (updatedRequired.includes(c)) {
            courseInfo[c] = { type: 'required', groupName: null };
        } else {
            for (const [gname, gdata] of Object.entries(groupConstraints)) {
                if (gdata.courses.includes(c)) {
                    courseInfo[c] = { type: 'group', groupName: gname };
                    break;
                }
            }
        }
    }

    // Precompute max credits per course
    const maxCreditsByCourse = {};
    for (const c of orderedCourses) {
        const courseSections = filteredSections[c] || [];
        maxCreditsByCourse[c] = courseSections.length > 0
            ? Math.max(...courseSections.map(s => s.credits))
            : 0.0;
    }

    // Initialize best schedule
    const best = { score: -1e9, schedule: null, credits: 0.0 };
    const initialChosen = [...lockedSections];
    const initialCredits = initialChosen.reduce((sum, s) => sum + s.credits, 0);
    const initialScore = initialChosen.reduce(
        (sum, s) => sum + scoreSection(s, facultyPrefs, dayTimePrefs),
        0
    );

    // Helper functions for schedule grid (track occupied time slots)
    function addToGrid(s, grid) {
        for (const d of s.days) {
            if (!grid[d]) grid[d] = new Set();
            for (let m = s.start; m < s.end; m++) {
                grid[d].add(m);
            }
        }
    }

    function removeFromGrid(s, grid) {
        for (const d of s.days) {
            if (grid[d]) {
                for (let m = s.start; m < s.end; m++) {
                    grid[d].delete(m);
                }
            }
        }
    }

    function isOverlap(s, grid) {
        for (const d of s.days) {
            if (grid[d]) {
                for (let m = s.start; m < s.end; m++) {
                    if (grid[d].has(m)) return true;
                }
            }
        }
        return false;
    }

    // Backtracking algorithm
    function backtrack(idx, chosen, currentScore, currentCredits, groupCounts, grid) {
        if (currentCredits > maxCredits) {
            return;
        }

        if (idx === orderedCourses.length) {
            // Check group constraints
            let allGroupsSatisfied = true;
            for (const [g, constraint] of Object.entries(groupConstraints)) {
                if ((groupCounts[g] || 0) < constraint.numRequired) {
                    allGroupsSatisfied = false;
                    break;
                }
            }

            if (allGroupsSatisfied && currentCredits >= minCredits) {
                const totalScore = currentScore - gapPenalty(chosen);
                if (totalScore > best.score) {
                    best.score = totalScore;
                    best.schedule = [...chosen];
                    best.credits = currentCredits;
                    if (callback) {
                        callback('best', 'SOLUTION', null, totalScore, [...chosen]);
                    }
                }
            }
            return;
        }

        const course = orderedCourses[idx];
        const info = courseInfo[course];
        const opts = filteredSections[course] || [];

        // Option 1: Skip course if allowed
        let canSkip = true;
        if (info.type === 'required') {
            canSkip = false;
        } else if (info.type === 'group') {
            const gname = info.groupName;
            const needed = groupConstraints[gname].numRequired - (groupCounts[gname] || 0);
            const remaining = orderedCourses.slice(idx + 1).filter(
                c2 => groupConstraints[gname].courses.includes(c2)
            ).length;
            if (remaining < needed) {
                canSkip = false;
            }
        }

        if (canSkip) {
            const remainingMax = orderedCourses.slice(idx + 1).reduce(
                (sum, c) => sum + (maxCreditsByCourse[c] || 0),
                0
            );
            if (currentCredits + remainingMax >= minCredits) {
                if (callback) {
                    callback('skip', course, null, currentScore, [...chosen]);
                }
                backtrack(idx + 1, chosen, currentScore, currentCredits, groupCounts, grid);
            }
        }

        // Option 2: Take each section
        for (const s of opts) {
            if (isOverlap(s, grid)) {
                continue;
            }

            const newCredits = currentCredits + s.credits;
            if (newCredits > maxCredits) {
                continue;
            }

            // Update group counts
            if (info.type === 'group') {
                const gname = info.groupName;
                if ((groupCounts[gname] || 0) >= groupConstraints[gname].numRequired) {
                    continue;
                }
                groupCounts[gname] = (groupCounts[gname] || 0) + 1;
            }

            // Place in grid
            addToGrid(s, grid);
            chosen.push(s);
            const sScore = scoreSection(s, facultyPrefs, dayTimePrefs);

            if (callback) {
                callback('try', s.course, s, currentScore + sScore, [...chosen]);
            }

            backtrack(idx + 1, chosen, currentScore + sScore, newCredits, groupCounts, grid);

            // Backtrack
            chosen.pop();
            removeFromGrid(s, grid);
            if (info.type === 'group') {
                const gname = info.groupName;
                groupCounts[gname]--;
                if (groupCounts[gname] === 0) {
                    delete groupCounts[gname];
                }
            }
        }
    }

    // Initialize grid and group counts
    const grid = {};
    for (const s of initialChosen) {
        addToGrid(s, grid);
    }

    const groupCounts = {};
    for (const s of initialChosen) {
        const info = courseInfo[s.course];
        if (info && info.type === 'group') {
            const gname = info.groupName;
            groupCounts[gname] = (groupCounts[gname] || 0) + 1;
        }
    }

    backtrack(0, [...initialChosen], initialScore, initialCredits, groupCounts, grid);

    return best;
}
