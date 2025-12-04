/**
 * Course Scheduler - Main Application Logic
 * Handles UI interactions, state management, and CSV parsing
 */

// Application state
const state = {
    sections: [],
    requiredCourses: [],
    courseGroups: [],
    facultyPrefs: {},
    dayTimePrefs: {
        M: { enabled: false, startTime: '08:00', endTime: '17:00', isRequirement: false },
        T: { enabled: false, startTime: '08:00', endTime: '17:00', isRequirement: false },
        W: { enabled: false, startTime: '08:00', endTime: '17:00', isRequirement: false },
        R: { enabled: false, startTime: '08:00', endTime: '17:00', isRequirement: false },
        F: { enabled: false, startTime: '08:00', endTime: '17:00', isRequirement: false },
        S: { enabled: false, startTime: '08:00', endTime: '17:00', isRequirement: false }
    },
    lockedSections: [],
    minCredits: 12,
    maxCredits: 18,
    selectedTableRows: [],
    currentGroup: null,
    lastSchedule: null,
    currentVisualizer: null  // Store current visualizer instance for real-time updates
};

// DOM elements
let elements = {};

/**
 * Initialize the application
 */
function init() {
    // Get DOM references
    elements = {
        uploadArea: document.getElementById('uploadArea'),
        csvFileInput: document.getElementById('csvFileInput'),
        browseBtn: document.getElementById('browseBtn'),
        existingFileSelect: document.getElementById('existingFileSelect'),
        loadExistingBtn: document.getElementById('loadExistingBtn'),
        filterInput: document.getElementById('filterInput'),
        courseTableBody: document.getElementById('courseTableBody'),
        statusBadge: document.getElementById('statusBadge'),
        coursesCount: document.getElementById('coursesCount'),
        sectionsCount: document.getElementById('sectionsCount'),

        // Required courses
        requiredCoursesList: document.getElementById('requiredCoursesList'),
        requiredCoursesCount: document.getElementById('requiredCoursesCount'),
        addRequiredBtn: document.getElementById('addRequiredBtn'),
        removeRequiredBtn: document.getElementById('removeRequiredBtn'),
        clearRequiredBtn: document.getElementById('clearRequiredBtn'),

        // Groups
        groupNameInput: document.getElementById('groupNameInput'),
        groupCountInput: document.getElementById('groupCountInput'),
        createGroupBtn: document.getElementById('createGroupBtn'),
        groupsList: document.getElementById('groupsList'),
        groupCoursesList: document.getElementById('groupCoursesList'),
        groupsStatus: document.getElementById('groupsStatus'),
        addToGroupBtn: document.getElementById('addToGroupBtn'),
        removeFromGroupBtn: document.getElementById('removeFromGroupBtn'),

        // Faculty preferences
        courseSelect: document.getElementById('courseSelect'),
        facultySelect: document.getElementById('facultySelect'),
        setPreferenceBtn: document.getElementById('setPreferenceBtn'),
        preferencesList: document.getElementById('preferencesList'),

        // Schedule preferences
        minCredits: document.getElementById('minCredits'),
        maxCredits: document.getElementById('maxCredits'),
        lockedSectionsList: document.getElementById('lockedSectionsList'),
        checklistItems: document.getElementById('checklistItems'),
        visualizeToggle: document.getElementById('visualizeToggle'),
        visualizationControls: document.getElementById('visualizationControls'),
        speedSlider: document.getElementById('speedSlider'),
        runSchedulerBtn: document.getElementById('runSchedulerBtn'),
        progressContainer: document.getElementById('progressContainer'),
        progressFill: document.getElementById('progressFill'),
        progressText: document.getElementById('progressText'),

        // Results
        resultsCard: document.getElementById('resultsCard'),
        resultsSummary: document.getElementById('resultsSummary'),
        resultsTableBody: document.getElementById('resultsTableBody'),
        exportCsvBtn: document.getElementById('exportCsvBtn'),
        viewVisualizationBtn: document.getElementById('viewVisualizationBtn'),

        // Modal
        visualizationModal: document.getElementById('visualizationModal'),
        scheduleGrid: document.getElementById('scheduleGrid'),
        closeVisualizationBtn: document.getElementById('closeVisualizationBtn'),

        // Context menu
        contextMenu: document.getElementById('contextMenu'),
        ctxAddRequired: document.getElementById('ctxAddRequired'),
        ctxLockSection: document.getElementById('ctxLockSection'),
        ctxViewDetails: document.getElementById('ctxViewDetails')
    };

    setupEventListeners();
    Toast.init();  // Initialize toast system
    updateChecklist();
    updateStatus('Ready to begin', 'success');
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // File upload
    elements.uploadArea.addEventListener('click', () => elements.csvFileInput.click());
    elements.browseBtn.addEventListener('click', () => elements.csvFileInput.click());
    elements.csvFileInput.addEventListener('change', handleFileSelect);

    // Existing file selection
    elements.loadExistingBtn.addEventListener('click', loadExistingFile);

    // Drag and drop
    elements.uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.add('drag-over');
    });
    elements.uploadArea.addEventListener('dragleave', () => {
        elements.uploadArea.classList.remove('drag-over');
    });
    elements.uploadArea.addEventListener('drop', handleFileDrop);

    // Filter
    elements.filterInput.addEventListener('input', refreshTable);

    // Table interactions
    elements.courseTableBody.addEventListener('click', handleTableClick);
    elements.courseTableBody.addEventListener('dblclick', handleTableDoubleClick);
    elements.courseTableBody.addEventListener('contextmenu', handleTableContextMenu);

    // Required courses
    elements.addRequiredBtn.addEventListener('click', addSelectedRequired);
    elements.removeRequiredBtn.addEventListener('click', removeSelectedRequired);
    elements.clearRequiredBtn.addEventListener('click', clearRequired);

    // Groups
    elements.createGroupBtn.addEventListener('click', createGroup);
    elements.groupsList.addEventListener('click', handleGroupSelect);
    elements.addToGroupBtn.addEventListener('click', addToGroup);
    elements.removeFromGroupBtn.addEventListener('click', removeFromGroup);

    // Faculty preferences
    elements.courseSelect.addEventListener('change', updateFacultyOptions);
    elements.setPreferenceBtn.addEventListener('click', setFacultyPreference);

    // Credits
    elements.minCredits.addEventListener('input', updateChecklist);
    elements.maxCredits.addEventListener('input', updateChecklist);

    // Time preferences
    document.querySelectorAll('.time-pref-card').forEach(card => {
        const day = card.dataset.day;
        const checkbox = card.querySelector('.day-enabled');
        const timeInputs = card.querySelectorAll('.time-input');
        const radios = card.querySelectorAll('input[type="radio"]');

        checkbox.addEventListener('change', () => updateTimePreference(day));
        timeInputs.forEach(input => input.addEventListener('change', () => updateTimePreference(day)));
        radios.forEach(radio => radio.addEventListener('change', () => updateTimePreference(day)));
    });

    // Visualization controls
    elements.visualizeToggle.addEventListener('change', () => {
        const isChecked = elements.visualizeToggle.checked;
        elements.visualizationControls.style.display = isChecked ? 'block' : 'none';
        updateChecklist();
    });

    // Run scheduler
    elements.runSchedulerBtn.addEventListener('click', runScheduler);

    // Results
    elements.exportCsvBtn.addEventListener('click', exportSchedule);
    elements.viewVisualizationBtn.addEventListener('click', showVisualization);

    // Modal
    elements.closeVisualizationBtn.addEventListener('click', closeVisualization);
    elements.visualizationModal.addEventListener('click', (e) => {
        if (e.target === elements.visualizationModal) closeVisualization();
    });

    // Context menu
    document.addEventListener('click', () => {
        elements.contextMenu.classList.remove('active');
    });
    elements.ctxAddRequired.addEventListener('click', () => {
        addSelectedRequired();
        elements.contextMenu.classList.remove('active');
    });
    elements.ctxLockSection.addEventListener('click', () => {
        lockSelectedSection();
        elements.contextMenu.classList.remove('active');
    });
    elements.ctxViewDetails.addEventListener('click', () => {
        showSectionDetails();
        elements.contextMenu.classList.remove('active');
    });
}

/**
 * Handle file selection
 */
function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        const fileExtension = file.name.toLowerCase().split('.').pop();
        if (['csv', 'xlsx', 'xls'].includes(fileExtension)) {
            if (fileExtension === 'csv') {
                loadCSVFile(file);
            } else {
                loadExcelFile(file);
            }
        } else {
            showError('Please select a CSV or Excel file (.csv, .xlsx, .xls)');
        }
    }
}

/**
 * Handle file drop
 */
function handleFileDrop(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('drag-over');

    const file = e.dataTransfer.files[0];
    if (file) {
        const fileExtension = file.name.toLowerCase().split('.').pop();
        if (['csv', 'xlsx', 'xls'].includes(fileExtension)) {
            if (fileExtension === 'csv') {
                loadCSVFile(file);
            } else {
                loadExcelFile(file);
            }
        } else {
            showError('Please drop a CSV or Excel file (.csv, .xlsx, .xls)');
        }
    } else {
        showError('Please drop a valid file');
    }
}

/**
 * Load and parse CSV file
 */
function loadCSVFile(file) {
    updateStatus('Loading file...', 'warning');
    
    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const text = e.target.result;
            parseCSV(text);
            showSuccess(`Loaded ${file.name} successfully!`);
        } catch (error) {
            console.error('CSV parsing error:', error);
            showError('Failed to parse CSV file: ' + error.message);
            updateStatus('Failed to load file', 'error');
        }
    };
    reader.onerror = () => {
        showError('Failed to read file');
        updateStatus('Failed to load file', 'error');
    };
    reader.readAsText(file);
}

/**
 * Parse CSV text
 */
function parseCSV(text) {
    const lines = text.trim().split('\n');
    if (lines.length < 2) {
        showError('CSV file appears to be empty');
        return;
    }

    // Parse header
    const headers = lines[0].split(',').map(h => h.trim().replace(/^"(.*)"$/, '$1'));

    // Parse rows
    const sections = [];
    for (let i = 1; i < lines.length; i++) {
        const values = parseCSVLine(lines[i]);
        if (values.length === 0) continue;

        const row = {};
        headers.forEach((header, idx) => {
            row[header] = values[idx] || '';
        });

        // Extract section data
        const course = (row['Course #'] || row['Course'] || '').trim();
        if (!course) continue;

        const sec = (row['Sec'] || '').trim();
        const faculty = (row['Faculty'] || '').trim();
        const days = parseDays(row['Days'] || row['Day'] || '');
        const start = parseTime(row['Start Time'] || row['Start'] || '');
        const end = parseTime(row['End Time'] || row['End'] || '');
        const creditStr = row['CR'] || row['Credits'] || row['Credit'] || '0';
        const credits = parseFloat(creditStr) || 0;

        const section = new Section(course, sec, faculty, days, start, end, credits, row);
        sections.push(section);
    }

    state.sections = sections;
    updateDataStatus();
    refreshTable();
    updateCourseOptions();
    updateChecklist();
    updateStatus('Ready to configure schedule', 'success');
}

/**
 * Parse a single CSV line (handles quoted values with commas)
 */
function parseCSVLine(line) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
        const char = line[i];

        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            values.push(current.trim().replace(/^"(.*)"$/, '$1'));
            current = '';
        } else {
            current += char;
        }
    }

    values.push(current.trim().replace(/^"(.*)"$/, '$1'));
    return values;
}

/**
 * Refresh the course table
 */
function refreshTable() {
    const tbody = elements.courseTableBody;
    tbody.innerHTML = '';

    const filter = elements.filterInput.value.toLowerCase().trim();
    const uniqueCourses = new Set();

    for (const section of state.sections) {
        // Apply filter
        if (filter) {
            const course = (section.course || '').toLowerCase();
            const faculty = (section.faculty || '').toLowerCase();
            const title = (section.raw['Course Title'] || '').toLowerCase();
            const remarks = (section.raw['Remarks'] || section.raw['Remark'] || '').toLowerCase();

            if (!course.includes(filter) && !faculty.includes(filter) &&
                !title.includes(filter) && !remarks.includes(filter)) {
                continue;
            }
        }

        const tr = document.createElement('tr');
        tr.dataset.index = state.sections.indexOf(section);

        const title = section.raw['Course Title'] || '';
        const room = section.raw['Room'] || '';

        tr.innerHTML = `
            <td>${section.course}</td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${title}">${title}</td>
            <td>${section.sec}</td>
            <td>${section.credits || ''}</td>
            <td>${section.faculty}</td>
            <td>${section.days.join('')}</td>
            <td>${minutesToStr(section.start)}</td>
            <td>${minutesToStr(section.end)}</td>
            <td>${room}</td>
        `;

        tbody.appendChild(tr);
        uniqueCourses.add(section.course);
    }

    if (tbody.children.length === 0) {
        tbody.innerHTML = '<tr class="no-data-row"><td colspan="9">No courses match your filter</td></tr>';
    }

    elements.coursesCount.textContent = uniqueCourses.size;
    elements.sectionsCount.textContent = state.sections.length;
}

/**
 * Update data status
 */ function updateDataStatus() {
    const uniqueCourses = new Set(state.sections.map(s => s.course));
    elements.coursesCount.textContent = uniqueCourses.size;
    elements.sectionsCount.textContent = state.sections.length;
}

/**
 * Handle table click (row selection)
 */
function handleTableClick(e) {
    const tr = e.target.closest('tr');
    if (!tr || !tr.dataset.index) return;

    if (e.ctrlKey || e.metaKey) {
        tr.classList.toggle('selected');
    } else {
        document.querySelectorAll('#courseTableBody tr.selected').forEach(row => {
            if (row !== tr) row.classList.remove('selected');
        });
        tr.classList.toggle('selected');
    }
}

/**
 * Handle table double-click (add to required)
 */
function handleTableDoubleClick(e) {
    const tr = e.target.closest('tr');
    if (!tr || !tr.dataset.index) return;

    const section = state.sections[parseInt(tr.dataset.index)];
    if (!state.requiredCourses.includes(section.course)) {
        state.requiredCourses.push(section.course);
        updateRequiredList();
        showSuccess(`Added ${section.course} to required courses`);
    }
}

/**
 * Handle table right-click (context menu)
 */
function handleTableContextMenu(e) {
    e.preventDefault();
    const tr = e.target.closest('tr');
    if (!tr || !tr.dataset.index) return;

    // Select this row
    document.querySelectorAll('#courseTableBody tr.selected').forEach(row => row.classList.remove('selected'));
    tr.classList.add('selected');

    // Show context menu
    elements.contextMenu.style.left = e.pageX + 'px';
    elements.contextMenu.style.top = e.pageY + 'px';
    elements.contextMenu.classList.add('active');
}

/**
 * Add selected courses to required list
 */
function addSelectedRequired() {
    const selected = document.querySelectorAll('#courseTableBody tr.selected');
    let added = 0;

    for (const tr of selected) {
        const section = state.sections[parseInt(tr.dataset.index)];
        if (!state.requiredCourses.includes(section.course)) {
            state.requiredCourses.push(section.course);
            added++;
        }
    }

    if (added > 0) {
        updateRequiredList();
        updateChecklist();
        showSuccess(`Added ${added} course(s) to required list`);
    } else {
        showInfo('Selected courses are already in the required list');
    }
}

/**
 * Remove selected courses from required list
 */
function removeSelectedRequired() {
    const selected = elements.requiredCoursesList.querySelector('li.selected');
    if (!selected) {
        showInfo('Please select a course to remove');
        return;
    }

    const course = selected.dataset.course;
    state.requiredCourses = state.requiredCourses.filter(c => c !== course);
    updateRequiredList();
    updateChecklist();
}

/**
 * Clear all required courses
 */
function clearRequired() {
    if (state.requiredCourses.length === 0) return;

    if (confirm('Clear all required courses?')) {
        state.requiredCourses = [];
        state.facultyPrefs = {};
        updateRequiredList();
        updatePreferencesList();
        updateChecklist();
    }
}

/**
 * Update required courses list display
 */
function updateRequiredList() {
    const list = elements.requiredCoursesList;
    list.innerHTML = '';

    if (state.requiredCourses.length === 0) {
        list.innerHTML = '<li class="empty-state">No required courses yet</li>';
        elements.requiredCoursesCount.textContent = '0 required courses selected';
    } else {
        for (const course of state.requiredCourses) {
            const li = document.createElement('li');
            li.dataset.course = course;

            // Find title
            const section = state.sections.find(s => s.course === course);
            const title = section?.raw['Course Title'] || '';
            li.textContent = title ? `${course} (${title.substring(0, 30)}${title.length > 30 ? '...' : ''})` : course;

            li.addEventListener('click', () => {
                list.querySelectorAll('li').forEach(item => item.classList.remove('selected'));
                li.classList.add('selected');
            });

            list.appendChild(li);
        }
        elements.requiredCoursesCount.textContent = `${state.requiredCourses.length} required courses selected`;
    }

    updateCourseOptions();
}

/**
 * Create a new course group
 */
function createGroup() {
    const name = elements.groupNameInput.value.trim();
    const count = parseInt(elements.groupCountInput.value);

    if (!name) {
        showError('Please enter a group name');
        return;
    }

    if (!count || count < 1) {
        showError('Please enter a valid number greater than 0');
        return;
    }

    if (state.courseGroups.some(g => g.name.toLowerCase() === name.toLowerCase())) {
        showError(`Group "${name}" already exists`);
        return;
    }

    const group = new CourseGroup(name, [], count);
    state.courseGroups.push(group);

    elements.groupNameInput.value = '';
    elements.groupCountInput.value = '1';

    updateGroupsList();
    updateChecklist();
    showSuccess(`Created group "${name}"`);
}

/**
 * Update groups list display
 */
function updateGroupsList() {
    const container = elements.groupsList;
    container.innerHTML = '';

    if (state.courseGroups.length === 0) {
        container.innerHTML = '<div class="empty-state">No groups created yet</div>';
        elements.groupsStatus.textContent = 'No groups created';
    } else {
        for (const group of state.courseGroups) {
            const div = document.createElement('div');
            div.className = 'group-item';
            div.dataset.groupName = group.name;

            div.innerHTML = `
                <h4>${group.name}</h4>
                <p>Need ${group.numRequired}, have ${group.courses.length} courses</p>
            `;

            div.addEventListener('click', () => selectGroup(group));
            container.appendChild(div);
        }

        const totalNeeded = state.courseGroups.reduce((sum, g) => sum + g.numRequired, 0);
        const totalCourses = state.courseGroups.reduce((sum, g) => sum + g.courses.length, 0);
        elements.groupsStatus.textContent = `${state.courseGroups.length} groups: need ${totalNeeded}, have ${totalCourses} available`;
    }
}

/**
 * Select a group for editing
 */
function selectGroup(group) {
    state.currentGroup = group;

    // Update UI
    document.querySelectorAll('.group-item').forEach(div => {
        div.classList.toggle('active', div.dataset.groupName === group.name);
    });

    updateGroupCoursesList();
}

/**
 * Handle group selection
 */
function handleGroupSelect(e) {
    const groupItem = e.target.closest('.group-item');
    if (!groupItem) return;

    const group = state.courseGroups.find(g => g.name === groupItem.dataset.groupName);
    if (group) selectGroup(group);
}

/**
 * Update group courses list
 */
function updateGroupCoursesList() {
    const list = elements.groupCoursesList;
    list.innerHTML = '';

    if (!state.currentGroup) {
        list.innerHTML = '<li class="empty-state">Select a group to manage courses</li>';
        return;
    }

    if (state.currentGroup.courses.length === 0) {
        list.innerHTML = '<li class="empty-state">No courses in this group yet</li>';
    } else {
        for (const course of state.currentGroup.courses) {
            const li = document.createElement('li');
            li.dataset.course = course;

            const section = state.sections.find(s => s.course === course);
            const title = section?.raw['Course Title'] || '';
            li.textContent = title ? `${course} (${title.substring(0, 25)}...)` : course;

            li.addEventListener('click', () => {
                list.querySelectorAll('li').forEach(item => item.classList.remove('selected'));
                li.classList.add('selected');
            });

            list.appendChild(li);
        }
    }
}

/**
 * Add selected courses to current group
 */
function addToGroup() {
    if (!state.currentGroup) {
        showInfo('Please select a group first');
        return;
    }

    const selected = document.querySelectorAll('#courseTableBody tr.selected');
    if (selected.length === 0) {
        showInfo('Please select courses from the table');
        return;
    }

    let added = 0;
    for (const tr of selected) {
        const section = state.sections[parseInt(tr.dataset.index)];
        if (state.requiredCourses.includes(section.course)) {
            continue; // Skip required courses
        }
        if (!state.currentGroup.courses.includes(section.course)) {
            state.currentGroup.courses.push(section.course);
            added++;
        }
    }

    updateGroupsList();
    updateGroupCoursesList();
    updateCourseOptions();

    if (added > 0) {
        showSuccess(`Added ${added} course(s) to ${state.currentGroup.name}`);
    }
}

/**
 * Remove selected courses from current group
 */
function removeFromGroup() {
    if (!state.currentGroup) return;

    const selected = elements.groupCoursesList.querySelector('li.selected');
    if (!selected) {
        showInfo('Please select a course to remove');
        return;
    }

    const course = selected.dataset.course;
    state.currentGroup.courses = state.currentGroup.courses.filter(c => c !== course);

    updateGroupsList();
    updateGroupCoursesList();
    updateCourseOptions();
}

/**
 * Update course options for faculty preferences
 */
function updateCourseOptions() {
    const select = elements.courseSelect;
    select.innerHTML = '<option value="">Select a course...</option>';

    // Get all courses (required + groups)
    const allCourses = new Set([...state.requiredCourses]);
    for (const group of state.courseGroups) {
        group.courses.forEach(c => allCourses.add(c));
    }

    // Filter to courses with multiple faculty options
    for (const course of Array.from(allCourses).sort()) {
        const faculties = new Set(
            state.sections.filter(s => s.course === course && s.faculty.trim()).map(s => s.faculty)
        );

        if (faculties.size > 1) {
            const option = document.createElement('option');
            option.value = course;
            const section = state.sections.find(s => s.course === course);
            const title = section?.raw['Course Title'] || '';
            option.textContent = title ? `${course} - ${title.substring(0, 40)}...` : course;
            select.appendChild(option);
        }
    }
}

/**
 * Update faculty options when course is selected
 */
function updateFacultyOptions() {
    const course = elements.courseSelect.value;
    const select = elements.facultySelect;
    select.innerHTML = '<option value="">Select faculty...</option>';

    if (!course) return;

    const faculties = new Set(
        state.sections.filter(s => s.course === course && s.faculty.trim()).map(s => s.faculty)
    );

    for (const faculty of Array.from(faculties).sort()) {
        const option = document.createElement('option');
        option.value = faculty;
        option.textContent = faculty;
        select.appendChild(option);
    }

    // Set current preference if exists
    if (state.facultyPrefs[course]) {
        select.value = state.facultyPrefs[course];
    }
}

/**
 * Set faculty preference
 */
function setFacultyPreference() {
    const course = elements.courseSelect.value;
    const faculty = elements.facultySelect.value;

    if (!course) {
        showInfo('Please select a course');
        return;
    }

    if (!faculty) {
        delete state.facultyPrefs[course];
    } else {
        state.facultyPrefs[course] = faculty;
    }

    updatePreferencesList();
    showSuccess(`Preference set for ${course}`);
}

/**
 * Update preferences list display
 */
function updatePreferencesList() {
    const list = elements.preferencesList;
    list.innerHTML = '';

    const prefs = Object.entries(state.facultyPrefs);
    if (prefs.length === 0) {
        list.innerHTML = '<li class="empty-state">No preferences set</li>';
    } else {
        for (const [course, faculty] of prefs) {
            const li = document.createElement('li');
            li.innerHTML = `<strong>${course}:</strong> ${faculty}`;
            list.appendChild(li);
        }
    }
}

/**
 * Update time preference for a specific day
 */
function updateTimePreference(day) {
    const card = document.querySelector(`.time-pref-card[data-day="${day}"]`);
    const enabled = card.querySelector('.day-enabled').checked;
    const startTime = card.querySelector('.start-time').value;
    const endTime = card.querySelector('.end-time').value;
    const isRequirement = card.querySelector('input[type="radio"][value="requirement"]').checked;

    state.dayTimePrefs[day] = {
        enabled,
        startTime,
        endTime,
        isRequirement
    };
}

/**
 * Lock selected section
 */
function lockSelectedSection() {
    const selected = document.querySelector('#courseTableBody tr.selected');
    if (!selected) return;

    const section = state.sections[parseInt(selected.dataset.index)];

    // Check if already locked
    if (state.lockedSections.some(s => s.course === section.course && s.sec === section.sec)) {
        showInfo('This section is already locked');
        return;
    }

    state.lockedSections.push(section);

    // Also add to required if not there
    if (!state.requiredCourses.includes(section.course)) {
        state.requiredCourses.push(section.course);
        updateRequiredList();
    }

    updateLockedList();
    updateChecklist();
    showSuccess(`Locked ${section.course} Sec ${section.sec}`);
}

/**
 * Update locked sections list
 */
function updateLockedList() {
    const list = elements.lockedSectionsList;
    list.innerHTML = '';

    if (state.lockedSections.length === 0) {
        list.innerHTML = '<li class="empty-state">No locked sections</li>';
    } else {
        for (const section of state.lockedSections) {
            const li = document.createElement('li');
            li.textContent = `${section.course} Sec ${section.sec} | ${section.faculty} | ${section.days.join('')} ${minutesToStr(section.start)}`;
            li.addEventListener('click', () => {
                if (confirm(`Unlock ${section.course} Sec ${section.sec}?`)) {
                    state.lockedSections = state.lockedSections.filter(s => s !== section);
                    updateLockedList();
                    updateChecklist();
                }
            });
            list.appendChild(li);
        }
    }
}

/**
 * Show section details
 */
function showSectionDetails() {
    const selected = document.querySelector('#courseTableBody tr.selected');
    if (!selected) return;

    const section = state.sections[parseInt(selected.dataset.index)];
    const details = `
<strong>${section.course}</strong> - Section ${section.sec}<br>
<strong>Faculty:</strong> ${section.faculty}<br>
<strong>Days:</strong> ${section.days.join(', ')}<br>
<strong>Time:</strong> ${minutesToStr(section.start)} - ${minutesToStr(section.end)}<br>
<strong>Credits:</strong> ${section.credits}<br>
<strong>Room:</strong> ${section.raw.Room || 'N/A'}
    `.trim();

    Toast.info(details, 8000);  // Show for 8 seconds since it's detailed info
}

/**
 * Update pre-flight checklist
 */
function updateChecklist() {
    const list = elements.checklistItems;
    list.innerHTML = '';

    const checks = [];

    // Check data loaded
    if (state.sections.length > 0) {
        checks.push({ icon: '✅', text: `Course data loaded (${state.sections.length} sections)`, status: true });
    } else {
        checks.push({ icon: '❌', text: 'No course data loaded', status: false });
    }

    // Check required courses or groups
    const hasRequirements = state.requiredCourses.length > 0 || state.courseGroups.length > 0 || state.lockedSections.length > 0;
    if (hasRequirements) {
        const parts = [];
        if (state.requiredCourses.length > 0) parts.push(`${state.requiredCourses.length} required`);
        if (state.courseGroups.length > 0) parts.push(`${state.courseGroups.length} groups`);
        if (state.lockedSections.length > 0) parts.push(`${state.lockedSections.length} locked`);
        checks.push({ icon: '✅', text: `Course selection: ${parts.join(', ')}`, status: true });
    } else {
        checks.push({ icon: '⚠️', text: 'No courses or groups selected', status: false });
    }

    // Check credit range
    const minCredits = parseInt(elements.minCredits.value);
    const maxCredits = parseInt(elements.maxCredits.value);
    if (!isNaN(minCredits) && !isNaN(maxCredits) && minCredits <= maxCredits && minCredits >= 0) {
        checks.push({ icon: '✅', text: `Credit range: ${minCredits}-${maxCredits}`, status: true });
    } else {
        checks.push({ icon: '❌', text: 'Invalid credit range', status: false });
    }

    // Display checklist
    let allGood = true;
    for (const check of checks) {
        if (!check.status && check.icon !== '⚠️') {
            allGood = false;
        }
        const li = document.createElement('li');
        li.className = check.status ? 'complete' : 'incomplete';
        li.textContent = `${check.icon} ${check.text}`;
        list.appendChild(li);
    }

    // Update run button
    elements.runSchedulerBtn.disabled = !allGood || !hasRequirements;
}

/** * Run the scheduler algorithm
 */
async function runScheduler() {
    const minCredits = parseFloat(elements.minCredits.value);
    const maxCredits = parseFloat(elements.maxCredits.value);
    const shouldVisualize = elements.visualizeToggle.checked;
    const speed = parseInt(elements.speedSlider.value);
    
    // Calculate delay based on speed (1=slow, 10=fast)
    const baseDelay = 2000; // 2 seconds base
    const delay = Math.max(100, baseDelay / speed);

    // Show progress
    elements.progressContainer.style.display = 'block';
    elements.progressText.textContent = 'Initializing algorithm...';
    elements.progressFill.style.width = '10%';
    elements.runSchedulerBtn.disabled = true;
    updateStatus('Generating schedule...', 'warning');

    // If visualization is enabled, show modal immediately
    if (shouldVisualize) {
        console.log('Opening visualization modal for algorithm progress');
        elements.visualizationModal.classList.add('active');
        state.currentVisualizer = new ScheduleVisualizer(elements.scheduleGrid);
        
        // Show initial empty state
        state.currentVisualizer.clear();
    }

    // Add delays to make the process visible
    await new Promise(resolve => setTimeout(resolve, delay));
    
    // Simulate progress steps
    elements.progressFill.style.width = '30%';
    elements.progressText.textContent = 'Analyzing course constraints...';
    await new Promise(resolve => setTimeout(resolve, delay));
    
    elements.progressFill.style.width = '50%';
    elements.progressText.textContent = 'Running optimization algorithm...';
    await new Promise(resolve => setTimeout(resolve, delay));

    // Simulate async execution
    setTimeout(async () => {
        try {
            const result = findBestSchedule(
                state.sections,
                state.requiredCourses,
                state.courseGroups,
                state.facultyPrefs,
                state.dayTimePrefs,
                state.lockedSections,
                minCredits,
                maxCredits,
                shouldVisualize ? visualizationCallback : null
            );

            // Show final progress
            elements.progressFill.style.width = '90%';
            elements.progressText.textContent = 'Finalizing schedule...';
            await new Promise(resolve => setTimeout(resolve, delay/2));

            elements.progressFill.style.width = '100%';
            elements.progressText.textContent = 'Complete!';

            setTimeout(async () => {
                elements.progressContainer.style.display = 'none';
                elements.runSchedulerBtn.disabled = false;
                
                // Close visualization modal if no schedule was found or visualization is off
                if (!result.schedule || result.schedule.length === 0 || !shouldVisualize) {
                    if (elements.visualizationModal.classList.contains('active')) {
                        elements.visualizationModal.classList.remove('active');
                    }
                }
                
                displayResults(result);
            }, 800);

        } catch (error) {
            console.error('Scheduling error:', error);
            elements.progressContainer.style.display = 'none';
            elements.runSchedulerBtn.disabled = false;
            
            // Close visualization modal on error
            if (elements.visualizationModal.classList.contains('active')) {
                elements.visualizationModal.classList.remove('active');
            }
            
            showError('Failed to generate schedule: ' + error.message);
            updateStatus('Scheduling failed', 'error');
        }
    }, delay);
}

/**
 * Visualization callback (for real-time algorithm visualization)
 */
function visualizationCallback(action, course, section, score, schedule) {
    console.log('Algorithm step:', action, course, score);
    
    // Show visualization modal if not already shown
    if (!elements.visualizationModal.classList.contains('active')) {
        elements.visualizationModal.classList.add('active');
        
        // Create visualizer instance
        state.currentVisualizer = new ScheduleVisualizer(elements.scheduleGrid);
    }
    
    // Update the visualization with current progress
    if (state.currentVisualizer && schedule) {
        state.currentVisualizer.drawSchedule(schedule);
        
        // Update progress text with algorithm details
        if (elements.progressText) {
            let statusText = `Analyzing ${course || 'courses'}...`;
            if (action === 'trying') {
                statusText = `Trying ${course} (Score: ${score?.toFixed(1) || '0'})`;
            } else if (action === 'backtrack') {
                statusText = `Backtracking from ${course}`;
            } else if (action === 'best') {
                statusText = `New best solution found! (Score: ${score?.toFixed(1) || '0'})`;
            }
            elements.progressText.textContent = statusText;
        }
    }
}

/**
 * Display scheduling results
 */
function displayResults(result) {
    console.log('displayResults called with:', result);
    
    if (!result.schedule || result.schedule.length === 0) {
        showError('No feasible schedule found. Try adjusting your requirements.');
        updateStatus('No schedule found', 'error');
        return;
    }

    state.lastSchedule = result.schedule;
    console.log('Schedule saved to state:', state.lastSchedule);

    // Show results card
    elements.resultsCard.style.display = 'block';
    elements.resultsCard.scrollIntoView({ behavior: 'smooth' });

    // Update summary
    const totalCourses = result.schedule.length;
    const totalCredits = result.credits.toFixed(1);
    const score = result.score.toFixed(1);

    elements.resultsSummary.innerHTML = `
        <div class="summary-card">
            <h4>Courses</h4>
            <p>${totalCourses}</p>
        </div>
        <div class="summary-card">
            <h4>Credits</h4>
            <p>${totalCredits}</p>
        </div>
        <div class="summary-card">
            <h4>Score</h4>
            <p>${score}</p>
        </div>
    `;

    // Update table
    const tbody = elements.resultsTableBody;
    tbody.innerHTML = '';

    for (const section of result.schedule) {
        const tr = document.createElement('tr');
        const title = section.raw['Course Title'] || '';
        const room = section.raw['Room'] || '';

        tr.innerHTML = `
            <td>${section.course}</td>
            <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;" title="${title}">${title}</td>
            <td>${section.sec}</td>
            <td>${section.faculty}</td>
            <td>${section.days.join('')}</td>
            <td>${minutesToStr(section.start)} - ${minutesToStr(section.end)}</td>
            <td>${room}</td>
            <td>${section.credits}</td>
        `;

        tbody.appendChild(tr);
    }

    updateStatus('Schedule generated successfully!', 'success');
    showSuccess(`Generated schedule with ${totalCourses} courses and ${totalCredits} credits!`);
}

/**
 * Export schedule to CSV
 */
function exportSchedule() {
    if (!state.lastSchedule || state.lastSchedule.length === 0) {
        showInfo('No schedule to export');
        return;
    }

    const headers = ['Course', 'Title', 'Sec', 'Faculty', 'Days', 'Start', 'End', 'Room', 'Credits'];
    const rows = [headers];

    for (const section of state.lastSchedule) {
        rows.push([
            section.course,
            section.raw['Course Title'] || '',
            section.sec,
            section.faculty,
            section.days.join(''),
            minutesToStr(section.start),
            minutesToStr(section.end),
            section.raw.Room || '',
            section.credits.toString()
        ]);
    }

    const csv = rows.map(row => row.map(cell => `"${cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'schedule.csv';
    a.click();
    URL.revokeObjectURL(url);

    showSuccess('Schedule exported to CSV');
}

/**
 * Show visualization modal
 */
function showVisualization() {
    console.log('showVisualization called');
    console.log('Last schedule:', state.lastSchedule);
    
    if (!state.lastSchedule || state.lastSchedule.length === 0) {
        showInfo('No schedule to visualize. Please generate a schedule first.');
        return;
    }

    console.log('Opening visualization modal');
    
    // Close any existing modal first
    if (elements.visualizationModal.classList.contains('active')) {
        elements.visualizationModal.classList.remove('active');
    }
    
    // Small delay to ensure clean state
    setTimeout(() => {
        elements.visualizationModal.classList.add('active');
        
        console.log('Creating visualizer');
        const visualizer = new ScheduleVisualizer(elements.scheduleGrid);
        visualizer.drawSchedule(state.lastSchedule);
        
        console.log('Visualization complete');
    }, 100);
}

/**
 * Close visualization modal
 */
function closeVisualization() {
    elements.visualizationModal.classList.remove('active');
}

/**
 * Update status badge
 */
function updateStatus(message, type = 'info') {
    const badge = elements.statusBadge;
    const text = badge.querySelector('.status-text');
    const dot = badge.querySelector('.status-dot');

    text.textContent = message;

    // Update dot color based on type
    const colors = {
        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
        error: 'var(--color-danger)',
        info: 'var(--color-primary)'
    };

    dot.style.background = colors[type] || colors.info;
}

/**
 * Toast notification system
 */
const Toast = {
    container: null,
    
    init() {
        this.container = document.getElementById('toastContainer');
    },
    
    show(message, type = 'info', duration = 4000) {
        if (!this.container) this.init();
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icons = {
            success: '✅',
            error: '❌',
            info: 'ℹ️'
        };
        
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || icons.info}</span>
            <span class="toast-content">${message}</span>
            <button class="toast-close" onclick="Toast.remove(this.parentElement)">&times;</button>
        `;
        
        this.container.appendChild(toast);
        
        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });
        
        // Auto remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.remove(toast);
            }, duration);
        }
        
        return toast;
    },
    
    remove(toast) {
        if (!toast || !toast.parentElement) return;
        
        toast.classList.remove('show');
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    },
    
    success(message, duration = 4000) {
        return this.show(message, 'success', duration);
    },
    
    error(message, duration = 6000) {
        return this.show(message, 'error', duration);
    },
    
    info(message, duration = 4000) {
        return this.show(message, 'info', duration);
    }
};

/**
 * Show success message
 */
function showSuccess(message) {
    Toast.success(message);
}

/**
 * Show info message
 */
function showInfo(message) {
    Toast.info(message);
}

/**
 * Show error message
 */
function showError(message) {
    Toast.error(message);
}

/**
 * Test function to manually trigger visualization (for debugging)
 */
window.testVisualization = function() {
    console.log('Testing visualization...');
    
    // Create a simple test schedule
    const testSchedule = [
        {
            course: 'CS101',
            sec: '01',
            faculty: 'Dr. Smith',
            days: ['M', 'W', 'F'],
            start: 540, // 9:00 AM
            end: 590,   // 9:50 AM
            credits: 3,
            raw: { 'Course Title': 'Introduction to Computer Science', Room: 'A101' }
        },
        {
            course: 'MATH201',
            sec: '02', 
            faculty: 'Dr. Johnson',
            days: ['T', 'R'],
            start: 660, // 11:00 AM
            end: 750,   // 12:30 PM
            credits: 4,
            raw: { 'Course Title': 'Calculus II', Room: 'B205' }
        }
    ];
    
    // Set test schedule
    state.lastSchedule = testSchedule;
    
    // Show visualization
    showVisualization();
};

console.log('Test function added: Call testVisualization() to test the modal');

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

/**
 * Load existing file from dropdown selection
 */
async function loadExistingFile() {
    const selectedFile = elements.existingFileSelect.value;
    if (!selectedFile) {
        showError('Please select a file from the dropdown');
        return;
    }

    try {
        updateStatus('Loading file...', 'warning');
        
        const response = await fetch(selectedFile);
        if (!response.ok) {
            throw new Error(`Failed to load file: ${response.statusText}`);
        }
        
        const text = await response.text();
        parseCSV(text);
        
        showSuccess(`Loaded ${selectedFile} successfully!`);
        
        // Reset the dropdown
        elements.existingFileSelect.value = '';
        
    } catch (error) {
        console.error('Error loading existing file:', error);
        showError(`Failed to load file: ${error.message}`);
        updateStatus('Failed to load file', 'error');
    }
}

/**
 * Load and parse Excel file
 */
function loadExcelFile(file) {
    showError('Excel file support requires additional library. Please convert to CSV format for now.');
    // Note: To fully support Excel, we would need to include a library like SheetJS
    // For now, we'll just show an error message directing users to convert to CSV
}
