/**
 * Schedule Visualizer
 * Creates an interactive schedule grid visualization
 */

class ScheduleVisualizer {
    constructor(containerEl) {
        console.log('ScheduleVisualizer constructor called with:', containerEl);
        this.container = containerEl;
        this.days = ['M', 'T', 'W', 'R', 'F', 'S'];
        this.dayLabels = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
        this.startHour = 7;
        this.endHour = 22;
        this.hourHeight = 50;
        this.dayWidth = 150;
        this.marginLeft = 80;
        this.marginTop = 50;

        // Color palette for courses
        this.colors = [
            '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
            '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88F', '#A1C299',
            '#FF8B94', '#C7CEEA', '#FFDAC1', '#B5EAD7', '#E2F0CB'
        ];
        this.courseColors = {};
        this.colorIndex = 0;

        console.log('Calling render()...');
        this.render();
        console.log('ScheduleVisualizer initialization complete');
    }

    getColor(course) {
        if (!this.courseColors[course]) {
            this.courseColors[course] = this.colors[this.colorIndex % this.colors.length];
            this.colorIndex++;
        }
        return this.courseColors[course];
    }

    render() {
        this.container.innerHTML = '';

        // Create SVG container
        const width = this.marginLeft + (this.days.length * this.dayWidth) + 20;
        const height = this.marginTop + ((this.endHour - this.startHour) * this.hourHeight) + 20;

        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('width', width);
        svg.setAttribute('height', height);
        svg.style.background = 'var(--bg-secondary)';
        svg.style.borderRadius = 'var(--border-radius)';

        // Draw time axis
        for (let h = this.startHour; h <= this.endHour; h++) {
            const y = this.marginTop + ((h - this.startHour) * this.hourHeight);

            // Time label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', this.marginLeft - 10);
            text.setAttribute('y', y + 5);
            text.setAttribute('text-anchor', 'end');
            text.setAttribute('fill', 'var(--text-secondary)');
            text.setAttribute('font-size', '12');
            text.textContent = `${h}:00`;
            svg.appendChild(text);

            // Horizontal grid line
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', this.marginLeft);
            line.setAttribute('y1', y);
            line.setAttribute('x2', this.marginLeft + (this.days.length * this.dayWidth));
            line.setAttribute('y2', y);
            line.setAttribute('stroke', 'var(--border-color)');
            line.setAttribute('stroke-width', '1');
            svg.appendChild(line);
        }

        // Draw day columns
        for (let i = 0; i < this.days.length; i++) {
            const x = this.marginLeft + (i * this.dayWidth);

            // Day label
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', x + (this.dayWidth / 2));
            text.setAttribute('y', this.marginTop - 20);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('fill', 'var(--text-primary)');
            text.setAttribute('font-size', '14');
            text.setAttribute('font-weight', '600');
            text.textContent = this.dayLabels[i];
            svg.appendChild(text);

            // Vertical grid line
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            line.setAttribute('x1', x);
            line.setAttribute('y1', this.marginTop);
            line.setAttribute('x2', x);
            line.setAttribute('y2', this.marginTop + ((this.endHour - this.startHour) * this.hourHeight));
            line.setAttribute('stroke', 'var(--border-color)');
            line.setAttribute('stroke-width', '1');
            svg.appendChild(line);
        }

        // Right border
        const rightX = this.marginLeft + (this.days.length * this.dayWidth);
        const rightLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        rightLine.setAttribute('x1', rightX);
        rightLine.setAttribute('y1', this.marginTop);
        rightLine.setAttribute('x2', rightX);
        rightLine.setAttribute('y2', this.marginTop + ((this.endHour - this.startHour) * this.hourHeight));
        rightLine.setAttribute('stroke', 'var(--border-color)');
        rightLine.setAttribute('stroke-width', '1');
        svg.appendChild(rightLine);

        this.svg = svg;
        this.container.appendChild(svg);
    }

    drawSchedule(schedule) {
        console.log('drawSchedule called with:', schedule);
        
        // Clear existing course blocks (keep grid)
        const existingBlocks = this.svg.querySelectorAll('.course-block, .course-text');
        console.log('Clearing', existingBlocks.length, 'existing blocks');
        existingBlocks.forEach(el => el.remove());

        if (!schedule || schedule.length === 0) {
            console.log('No schedule provided, showing empty message');
            // Show "No schedule" message
            const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            text.setAttribute('x', this.marginLeft + (this.days.length * this.dayWidth) / 2);
            text.setAttribute('y', this.marginTop + ((this.endHour - this.startHour) * this.hourHeight) / 2);
            text.setAttribute('text-anchor', 'middle');
            text.setAttribute('fill', 'var(--text-muted)');
            text.setAttribute('font-size', '16');
            text.setAttribute('font-style', 'italic');
            text.textContent = 'No schedule generated yet';
            text.classList.add('course-text');
            this.svg.appendChild(text);
            return;
        }

        console.log('Drawing', schedule.length, 'course sections');
        // Draw course blocks
        for (const section of schedule) {
            if (section.start === null || section.end === null) continue;

            const color = this.getColor(section.course);
            const startH = section.start / 60;
            const endH = section.end / 60;

            // Clamp to visible range
            const clampedStart = Math.max(this.startHour, startH);
            const clampedEnd = Math.min(this.endHour, endH);

            if (clampedStart >= clampedEnd) continue;

            const y1 = this.marginTop + ((clampedStart - this.startHour) * this.hourHeight);
            const y2 = this.marginTop + ((clampedEnd - this.startHour) * this.hourHeight);
            const blockHeight = y2 - y1;

            for (const day of section.days) {
                const dayIndex = this.days.indexOf(day);
                if (dayIndex === -1) continue;

                const x = this.marginLeft + (dayIndex * this.dayWidth);

                // Course block rectangle
                const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', x + 4);
                rect.setAttribute('y', y1 + 2);
                rect.setAttribute('width', this.dayWidth - 8);
                rect.setAttribute('height', blockHeight - 4);
                rect.setAttribute('fill', color);
                rect.setAttribute('opacity', '0.9');
                rect.setAttribute('rx', '6');
                rect.classList.add('course-block');

                // Add hover effect
                rect.style.cursor = 'pointer';
                rect.style.transition = 'opacity 0.2s';
                rect.addEventListener('mouseenter', () => {
                    rect.setAttribute('opacity', '1');
                });
                rect.addEventListener('mouseleave', () => {
                    rect.setAttribute('opacity', '0.9');
                });

                // Tooltip
                const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                const courseTitle = section.raw['Course Title'] || '';
                title.textContent = `${section.course}${courseTitle ? ' - ' + courseTitle : ''}\nSection: ${section.sec}\n${section.faculty}\n${minutesToStr(section.start)} - ${minutesToStr(section.end)}\nRoom: ${section.raw.Room || 'N/A'}`;
                rect.appendChild(title);

                this.svg.appendChild(rect);

                // Course label
                const textY = y1 + 16;
                const textX = x + (this.dayWidth / 2);

                // Course code
                const courseText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                courseText.setAttribute('x', textX);
                courseText.setAttribute('y', textY);
                courseText.setAttribute('text-anchor', 'middle');
                courseText.setAttribute('fill', '#000');
                courseText.setAttribute('font-size', '11');
                courseText.setAttribute('font-weight', '700');
                courseText.textContent = section.course;
                courseText.classList.add('course-text');
                courseText.style.pointerEvents = 'none';
                this.svg.appendChild(courseText);

                // Section number
                if (blockHeight > 30) {
                    const secText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    secText.setAttribute('x', textX);
                    secText.setAttribute('y', textY + 14);
                    secText.setAttribute('text-anchor', 'middle');
                    secText.setAttribute('fill', '#000');
                    secText.setAttribute('font-size', '9');
                    secText.textContent = `Sec: ${section.sec}`;
                    secText.classList.add('course-text');
                    secText.style.pointerEvents = 'none';
                    this.svg.appendChild(secText);
                }

                // Time
                if (blockHeight > 50) {
                    const timeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                    timeText.setAttribute('x', textX);
                    timeText.setAttribute('y', textY + 28);
                    timeText.setAttribute('text-anchor', 'middle');
                    timeText.setAttribute('fill', '#000');
                    timeText.setAttribute('font-size', '8');
                    timeText.textContent = `${minutesToStr(section.start)}`;
                    timeText.classList.add('course-text');
                    timeText.style.pointerEvents = 'none';
                    this.svg.appendChild(timeText);
                }
            }
        }
    }

    clear() {
        this.drawSchedule([]);
    }
}

/**
 * Create HTML-based schedule visualization (alternative to SVG)
 */
function createHTMLScheduleView(schedule) {
    const container = document.createElement('div');
    container.className = 'schedule-table-view';
    container.style.cssText = `
        display: grid;
        grid-template-columns: 80px repeat(6, 1fr);
        gap: 1px;
        background: var(--border-color);
        border-radius: var(--border-radius);
        overflow: hidden;
    `;

    const days = ['M', 'T', 'W', 'R', 'F', 'S'];
    const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    // Header row
    const headerCorner = document.createElement('div');
    headerCorner.style.cssText = 'background: var(--bg-tertiary); padding: 0.5rem; font-weight: 600;';
    headerCorner.textContent = 'Time';
    container.appendChild(headerCorner);

    for (const dayLabel of dayLabels) {
        const header = document.createElement('div');
        header.style.cssText = 'background: var(--bg-tertiary); padding: 0.5rem; font-weight: 600; text-align: center;';
        header.textContent = dayLabel;
        container.appendChild(header);
    }

    // Group courses by day and time
    const coursesByDay = {};
    for (const day of days) {
        coursesByDay[day] = [];
    }

    for (const section of schedule) {
        for (const day of section.days) {
            if (coursesByDay[day]) {
                coursesByDay[day].push(section);
            }
        }
    }

    // Sort courses by start time
    for (const day of days) {
        coursesByDay[day].sort((a, b) => (a.start || 0) - (b.start || 0));
    }

    // Create time slots (8 AM to 6 PM)
    const startHour = 8;
    const endHour = 18;

    for (let hour = startHour; hour <= endHour; hour++) {
        // Time label
        const timeLabel = document.createElement('div');
        timeLabel.style.cssText = 'background: var(--bg-secondary); padding: 0.5rem; font-size: 0.875rem; color: var(--text-secondary);';
        timeLabel.textContent = `${hour}:00`;
        container.appendChild(timeLabel);

        // Day cells
        for (const day of days) {
            const cell = document.createElement('div');
            cell.style.cssText = 'background: var(--bg-secondary); padding: 0.25rem; min-height: 50px; position: relative;';

            // Find courses in this time slot
            const coursesInSlot = coursesByDay[day].filter(s => {
                const sStart = Math.floor((s.start || 0) / 60);
                const sEnd = Math.ceil((s.end || 0) / 60);
                return sStart <= hour && sEnd > hour;
            });

            if (coursesInSlot.length > 0) {
                for (const section of coursesInSlot) {
                    const courseBlock = document.createElement('div');
                    courseBlock.style.cssText = `
                        background: linear-gradient(135deg, var(--color-primary), var(--color-secondary));
                        padding: 0.25rem;
                        border-radius: 4px;
                        font-size: 0.75rem;
                        margin-bottom: 2px;
                        color: white;
                        font-weight: 600;
                    `;
                    courseBlock.textContent = `${section.course} (${section.sec})`;
                    courseBlock.title = `${section.faculty}\n${minutesToStr(section.start)} - ${minutesToStr(section.end)}`;
                    cell.appendChild(courseBlock);
                }
            }

            container.appendChild(cell);
        }
    }

    return container;
}
