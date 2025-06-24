/**
 * Rainbow Towers Conference Booking System
 * Main JavaScript File
 * 
 * This file contains all the client-side functionality for the conference booking system,
 * including calendar management, form handling, data visualization, and UI enhancements.
 * 
 * @version 1.0
 */

// ===== GLOBAL VARIABLES AND CONSTANTS =====
const SYSTEM = {
    name: 'Rainbow Towers Booking System',
    version: '1.0',
    dateFormat: 'YYYY-MM-DD',
    timeFormat: 'HH:mm',
    currency: 'USD',
    locale: 'en-US',
    autoLogoutTime: 30 * 60 * 1000, // 30 minutes
    defaultView: 'dayGridMonth',
    workingHours: {
        start: '07:00',
        end: '22:00'
    },
    statusColors: {
        tentative: '#f6c23e',
        confirmed: '#1cc88a',
        cancelled: '#e74a3b'
    },
    notificationSounds: {
        success: new Audio('/static/sounds/success.mp3'),
        error: new Audio('/static/sounds/error.mp3'),
        notification: new Audio('/static/sounds/notification.mp3')
    },
    debounceTime: 300, // ms for debounce function
    animationDuration: 300, // ms for animations
    toastDuration: 3000 // ms for toast notifications
};

// ===== INITIALIZATION =====
document.addEventListener('DOMContentLoaded', function() {
    // Initialize core components
    initializeUI();
    initializeCalendar();
    setupForms();
    initializeDataTables();
    setupRealTimeUpdates();
    
    // Initialize feature-specific components
    initBookingFeatures();
    initClientFeatures();
    initRoomFeatures();
    initAddonFeatures();
    initReportFeatures();
    
    // Set up global event handlers
    setupGlobalEventListeners();
    
    // Check if dashboard and initialize dashboard widgets
    if (document.getElementById('dashboard-stats')) {
        initializeDashboardWidgets();
    }
    
    // Enable tooltips, popovers, and toasts
    enableBootstrapComponents();
    
    // Initialize security features
    setupSecurityFeatures();
    
    console.log(`${SYSTEM.name} v${SYSTEM.version} initialized successfully`);
});

// ===== CORE FUNCTIONS =====

/**
 * Initialize UI components and global styles
 */
function initializeUI() {
    // Add fade-in effect to main content
    const mainContent = document.querySelector('.container');
    if (mainContent) {
        mainContent.classList.add('fade-in');
    }
    
    // Initialize mobile navigation
    const navbarToggler = document.querySelector('.navbar-toggler');
    const navbarMenu = document.querySelector('.navbar-collapse');
    
    if (navbarToggler && navbarMenu) {
        // Handle menu toggle
        navbarToggler.addEventListener('click', function() {
            if (window.innerWidth < 992) { // Only for mobile
                document.body.classList.toggle('menu-open');
            }
        });
        
        // Close menu when clicking on mobile menu items
        const navItems = navbarMenu.querySelectorAll('.nav-link');
        navItems.forEach(item => {
            item.addEventListener('click', function() {
                if (window.innerWidth < 992 && navbarMenu.classList.contains('show')) {
                    const bsCollapse = bootstrap.Collapse.getInstance(navbarMenu);
                    if (bsCollapse) {
                        bsCollapse.hide();
                    }
                }
            });
        });
    }
    
    // Handle theme preference toggle if present
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
        
        // Set initial theme based on local storage or system preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.body.classList.add('dark-theme');
            themeToggle.checked = true;
        }
    }
    
    // Initialize dropdown menus with search capability
    initializeSearchableDropdowns();
    
    // Handle print button functionality
    setupPrintButtons();
    
    // Setup custom scrollbars
    setupCustomScrollbars();
    
    // Handle fixed header on scroll
    handleFixedHeader();
    
    // Initialize notifications bell
    initializeNotificationSystem();
    
    // Handle back to top button
    setupBackToTopButton();
}

/**
 * Enable all Bootstrap components
 */
function enableBootstrapComponents() {
    // Enable tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-hide alerts after 5 seconds
    const autoHideAlerts = document.querySelectorAll('.alert-dismissible');
    autoHideAlerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 5000);
    });
}

/**
 * Initialize the booking calendar if it exists on the page
 */
function initializeCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    // Set up calendar options
    const calendarOptions = {
        initialView: SYSTEM.defaultView,
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        allDaySlot: false,
        slotMinTime: SYSTEM.workingHours.start,
        slotMaxTime: SYSTEM.workingHours.end,
        businessHours: {
            daysOfWeek: [0, 1, 2, 3, 4, 5, 6], // Sunday to Saturday
            startTime: SYSTEM.workingHours.start,
            endTime: SYSTEM.workingHours.end
        },
        height: '100%',
        events: getEventsEndpoint(),
        eventClick: function(info) {
            showEventDetails(info.event);
        },
        dateClick: function(info) {
            handleDateClick(info);
        },
        eventDrop: function(info) {
            handleEventDrop(info);
        },
        eventResize: function(info) {
            handleEventResize(info);
        },
        loading: function(isLoading) {
            toggleCalendarLoading(isLoading);
        },
        eventTimeFormat: {
            hour: '2-digit',
            minute: '2-digit',
            meridiem: false,
            hour12: false
        },
        eventClassNames: function(arg) {
            return [`event-${arg.event.extendedProps.status}`];
        },
        eventContent: function(arg) {
            return createCustomEventContent(arg);
        },
        datesSet: function(dateInfo) {
            updateFilteredDateRange(dateInfo);
        }
    };
    
    // Initialize FullCalendar
    const calendar = new FullCalendar.Calendar(calendarEl, calendarOptions);
    calendar.render();
    
    // Store calendar in global scope for external access
    window.bookingCalendar = calendar;
    
    // Initialize calendar filters
    initializeCalendarFilters(calendar);
    
    // Initialize drag and drop functionality for new bookings
    initializeDragAndDrop(calendar);
    
    // Add export functionality
    addCalendarExportButtons(calendar);
    
    // Add bulk actions menu
    addBulkActionMenu(calendar);
    
    // Set up calendar keyboard shortcuts
    setupCalendarKeyboardShortcuts(calendar);
}

/**
 * Initialize calendar filters
 * @param {Object} calendar - The FullCalendar instance
 */
function initializeCalendarFilters(calendar) {
    // Room filter
    const roomFilter = document.getElementById('roomFilter');
    if (roomFilter) {
        roomFilter.addEventListener('change', function() {
            filterCalendarEvents();
        });
    }
    
    // Status filters
    const statusCheckboxes = document.querySelectorAll('input[type=checkbox][id^="status"]');
    statusCheckboxes.forEach(function(checkbox) {
        checkbox.addEventListener('change', function() {
            filterCalendarEvents();
        });
    });
    
    // View buttons
    const viewButtons = {
        month: document.getElementById('viewMonthBtn'),
        week: document.getElementById('viewWeekBtn'),
        day: document.getElementById('viewDayBtn')
    };
    
    if (viewButtons.month) {
        viewButtons.month.addEventListener('click', function() {
            calendar.changeView('dayGridMonth');
            updateActiveViewButton('month');
        });
    }
    
    if (viewButtons.week) {
        viewButtons.week.addEventListener('click', function() {
            calendar.changeView('timeGridWeek');
            updateActiveViewButton('week');
        });
    }
    
    if (viewButtons.day) {
        viewButtons.day.addEventListener('click', function() {
            calendar.changeView('timeGridDay');
            updateActiveViewButton('day');
        });
    }
    
    // Set initial active button
    updateActiveViewButton('month');
    
    // Initialize date range filter if present
    initializeDateRangeFilter(calendar);
    
    // Apply initial filters
    filterCalendarEvents();
}

/**
 * Filter calendar events based on selected options
 */
function filterCalendarEvents() {
    if (!window.bookingCalendar) return;
    
    const roomId = document.getElementById('roomFilter')?.value || 'all';
    const statusTentative = document.getElementById('statusTentative')?.checked || false;
    const statusConfirmed = document.getElementById('statusConfirmed')?.checked || false;
    const statusCancelled = document.getElementById('statusCancelled')?.checked || false;
    
    // Get all events
    const events = window.bookingCalendar.getEvents();
    
    // Apply filters
    events.forEach(function(event) {
        let shouldShow = true;
        
        // Filter by room
        if (roomId !== 'all' && event.extendedProps.roomId != roomId) {
            shouldShow = false;
        }
        
        // Filter by status
        const eventStatus = event.extendedProps.status;
        if ((eventStatus === 'tentative' && !statusTentative) ||
            (eventStatus === 'confirmed' && !statusConfirmed) ||
            (eventStatus === 'cancelled' && !statusCancelled)) {
            shouldShow = false;
        }
        
        // Apply visibility
        event.setProp('display', shouldShow ? 'auto' : 'none');
    });
    
    // Update counters in the UI
    updateEventCounters();
}

/**
 * Handle showing event details modal
 * @param {Object} event - FullCalendar event object
 */
function showEventDetails(event) {
    // Create or get the modal
    let modal = document.getElementById('eventModal');
    if (!modal) {
        modal = createEventModal();
    }
    
    // Get the Bootstrap modal instance or create it
    let modalInstance = bootstrap.Modal.getInstance(modal);
    if (!modalInstance) {
        modalInstance = new bootstrap.Modal(modal);
    }
    
    // Format dates
    const start = new Date(event.start);
    const end = new Date(event.end);
    
    const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    const timeOptions = { hour: '2-digit', minute: '2-digit', hour12: false };
    
    // Populate modal with event details
    modal.querySelector('#eventTitle').textContent = event.title;
    
    // Set status badge
    const statusBadge = modal.querySelector('#eventStatus');
    const status = event.extendedProps.status;
    statusBadge.textContent = capitalizeFirstLetter(status);
    statusBadge.className = `badge bg-${getStatusClass(status)}`;
    
    // Set other event details
    modal.querySelector('#eventDate').textContent = start.toLocaleDateString(SYSTEM.locale, dateOptions);
    modal.querySelector('#eventTime').textContent = `${start.toLocaleTimeString(SYSTEM.locale, timeOptions)} - ${end.toLocaleTimeString(SYSTEM.locale, timeOptions)}`;
    modal.querySelector('#eventRoom').textContent = event.extendedProps.room;
    modal.querySelector('#eventClient').textContent = event.extendedProps.client;
    modal.querySelector('#eventAttendees').textContent = event.extendedProps.attendees || 'Not specified';
    
    // Notes with fallback
    const notesElement = modal.querySelector('#eventNotes');
    if (event.extendedProps.notes) {
        notesElement.textContent = event.extendedProps.notes;
        notesElement.classList.remove('text-muted');
    } else {
        notesElement.textContent = 'No notes available';
        notesElement.classList.add('text-muted');
    }
    
    // Set action links
    modal.querySelector('#viewBookingLink').href = `/bookings/${event.id}`;
    modal.querySelector('#editBookingLink').href = `/bookings/${event.id}/edit`;
    
    // Show the modal
    modalInstance.show();
    
    // Animate entrance for better UX
    setTimeout(() => {
        modal.querySelector('.modal-content').classList.add('scale-in');
    }, 50);
}

/**
 * Initialize form functionality and validation
 */
function setupForms() {
    // Initialize all form validations
    setupFormValidation();
    
    // Initialize datetime pickers
    initializeDateTimePickers();
    
    // Initialize select2 for searchable dropdowns
    initializeSelect2Dropdowns();
    
    // Set up dynamic form elements
    setupDynamicFormElements();
    
    // Prevent accidental navigation away from forms with changes
    setupFormNavigationWarnings();
    
    // Initialize specific form behavior for booking form
    initializeBookingForm();
    
    // Initialize specific form behavior for room form
    initializeRoomForm();
    
    // Initialize specific form behavior for client form
    initializeClientForm();
    
    // Initialize specific form behavior for addon form
    initializeAddonForm();
    
    // Setup form autosave functionality
    setupFormAutosave();
}

/**
 * Initialize date and time pickers for forms
 */
function initializeDateTimePickers() {
    // Date pickers (single date)
    if (typeof flatpickr !== 'undefined') {
        flatpickr('.datepicker', {
            dateFormat: 'Y-m-d',
            allowInput: true,
            altInput: true,
            altFormat: 'F j, Y',
            locale: SYSTEM.locale.substring(0, 2),
            disableMobile: true
        });
        
        // Time pickers
        flatpickr('.timepicker', {
            enableTime: true,
            noCalendar: true,
            dateFormat: 'H:i',
            time_24hr: true,
            minuteIncrement: 15,
            allowInput: true,
            disableMobile: true
        });
        
        // Date & time pickers
        flatpickr('.datetimepicker', {
            enableTime: true,
            dateFormat: 'Y-m-d H:i',
            time_24hr: true,
            minuteIncrement: 15,
            allowInput: true,
            altInput: true,
            altFormat: 'F j, Y - H:i',
            locale: SYSTEM.locale.substring(0, 2),
            disableMobile: true,
            // Disable past dates
            minDate: 'today',
            // Define business hours
            "enable": [
                function(date) {
                    const start = SYSTEM.workingHours.start.split(':');
                    const end = SYSTEM.workingHours.end.split(':');
                    const startTime = parseInt(start[0]) * 60 + parseInt(start[1]);
                    const endTime = parseInt(end[0]) * 60 + parseInt(end[1]);
                    const currentTime = date.getHours() * 60 + date.getMinutes();
                    
                    return currentTime >= startTime && currentTime <= endTime;
                }
            ]
        });
        
        // Date range picker
        flatpickr('.daterangepicker', {
            mode: 'range',
            dateFormat: 'Y-m-d',
            allowInput: true,
            altInput: true,
            altFormat: 'F j, Y',
            locale: SYSTEM.locale.substring(0, 2),
            disableMobile: true
        });
    }
}

/**
 * Initialize Select2 for searchable dropdowns
 */
function initializeSelect2Dropdowns() {
    if (typeof $.fn.select2 !== 'undefined') {
        $('.select2').select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: 'Select an option',
            allowClear: true
        });
        
        // Initialize client select with AJAX for better performance
        $('.select2-clients').select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: 'Search for a client',
            allowClear: true,
            minimumInputLength: 2,
            ajax: {
                url: '/api/clients/search',
                dataType: 'json',
                delay: 250,
                data: function(params) {
                    return {
                        q: params.term
                    };
                },
                processResults: function(data) {
                    return {
                        results: data.map(client => ({
                            id: client.id,
                            text: client.company_name ? `${client.company_name} (${client.contact_person})` : client.contact_person
                        }))
                    };
                },
                cache: true
            }
        });
        
        // Initialize room select with room capacity indicator
        $('.select2-rooms').select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: 'Select a conference room',
            allowClear: true,
            templateResult: formatRoomOption,
            templateSelection: formatRoomSelection
        });
        
        // Initialize add-ons multi-select
        $('.select2-addons').select2({
            theme: 'bootstrap-5',
            width: '100%',
            placeholder: 'Select add-on services',
            closeOnSelect: false,
            templateResult: formatAddonOption,
            templateSelection: formatAddonSelection
        });
    }
}

/**
 * Format room option in select dropdown
 * @param {Object} room - Room option data
 * @returns {HTMLElement} - Formatted option element
 */
function formatRoomOption(room) {
    if (!room.id) return room.text;
    
    const capacity = $(room.element).data('capacity');
    const rate = $(room.element).data('rate');
    
    return $(`
        <div class="d-flex align-items-center">
            <div class="me-auto">
                <strong>${room.text}</strong>
                <div class="small text-muted">Capacity: ${capacity} people</div>
            </div>
            <div class="text-end">
                <span class="badge bg-primary">$${rate}/hr</span>
            </div>
        </div>
    `);
}

/**
 * Format room selection in select dropdown
 * @param {Object} room - Selected room data
 * @returns {string} - Formatted selection text
 */
function formatRoomSelection(room) {
    if (!room.id) return room.text;
    
    const capacity = $(room.element).data('capacity');
    return `${room.text} (${capacity} people)`;
}

/**
 * Format add-on option in multi-select dropdown
 * @param {Object} addon - Add-on option data
 * @returns {HTMLElement} - Formatted option element
 */
function formatAddonOption(addon) {
    if (!addon.id) return addon.text;
    
    const category = $(addon.element).data('category');
    const price = $(addon.element).data('price');
    
    return $(`
        <div class="d-flex align-items-center py-1">
            <div class="me-auto">
                <strong>${addon.text}</strong>
                <div class="small text-muted">${category}</div>
            </div>
            <div class="ms-3">
                <span class="badge bg-primary">$${price}</span>
            </div>
        </div>
    `);
}

/**
 * Format add-on selection in multi-select dropdown
 * @param {Object} addon - Selected add-on data
 * @returns {string} - Formatted selection text
 */
function formatAddonSelection(addon) {
    if (!addon.id) return addon.text;
    
    const price = $(addon.element).data('price');
    return `${addon.text} ($${price})`;
}

/**
 * Setup form validation
 */
function setupFormValidation() {
    // Get all forms with validation class
    const forms = document.querySelectorAll('.needs-validation');
    
    // Setup validation behavior
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Highlight first invalid field and scroll to it
                const firstInvalidField = form.querySelector(':invalid');
                if (firstInvalidField) {
                    firstInvalidField.focus();
                    
                    const fieldTop = firstInvalidField.getBoundingClientRect().top;
                    const offsetTop = fieldTop + window.pageYOffset - 100;
                    window.scrollTo({top: offsetTop, behavior: 'smooth'});
                    
                    // Highlight the field
                    firstInvalidField.classList.add('highlight-invalid');
                    setTimeout(() => {
                        firstInvalidField.classList.remove('highlight-invalid');
                    }, 1500);
                }
                
                // Show validation toast notification
                showToast('Please check the form for errors', 'error');
            } else {
                // Add loading state to submit button
                const submitBtn = form.querySelector('[type="submit"]');
                if (submitBtn) {
                    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Processing...';
                    submitBtn.disabled = true;
                }
            }
            
            form.classList.add('was-validated');
        }, false);
        
        // Custom validation for password match
        const password = form.querySelector('#password');
        const confirmPassword = form.querySelector('#confirmPassword');
        
        if (password && confirmPassword) {
            confirmPassword.addEventListener('input', function() {
                if (password.value !== confirmPassword.value) {
                    confirmPassword.setCustomValidity('Passwords do not match');
                } else {
                    confirmPassword.setCustomValidity('');
                }
            });
            
            password.addEventListener('input', function() {
                if (password.value !== confirmPassword.value) {
                    confirmPassword.setCustomValidity('Passwords do not match');
                } else {
                    confirmPassword.setCustomValidity('');
                }
            });
        }
        
        // Custom validation for time range
        const startTime = form.querySelector('#start_time');
        const endTime = form.querySelector('#end_time');
        
        if (startTime && endTime) {
            const validateTimeRange = function() {
                if (startTime.value && endTime.value) {
                    const start = new Date(startTime.value);
                    const end = new Date(endTime.value);
                    
                    if (end <= start) {
                        endTime.setCustomValidity('End time must be after start time');
                    } else {
                        endTime.setCustomValidity('');
                    }
                }
            };
            
            startTime.addEventListener('change', validateTimeRange);
            endTime.addEventListener('change', validateTimeRange);
        }
    });
}

/**
 * Initialize booking form with special functionality
 */
function initializeBookingForm() {
    const bookingForm = document.getElementById('bookingForm');
    if (!bookingForm) return;
    
    // Get relevant form elements
    const roomSelect = document.getElementById('roomSelect');
    const startTimeInput = document.querySelector('input[name="start_time"]');
    const endTimeInput = document.querySelector('input[name="end_time"]');
    const attendeesInput = document.querySelector('input[name="attendees"]');
    const discountInput = document.querySelector('input[name="discount"]');
    
    // Set up room availability check
    if (roomSelect && startTimeInput && endTimeInput) {
        const checkRoomAvailability = debounce(function() {
            const roomId = roomSelect.value;
            const startTime = startTimeInput.value;
            const endTime = endTimeInput.value;
            const bookingId = bookingForm.dataset.bookingId || '';
            
            if (!roomId || !startTime || !endTime) return;
            
            const statusElem = document.getElementById('roomAvailabilityStatus');
            if (!statusElem) return;
            
            statusElem.innerHTML = '<div class="spinner-border spinner-border-sm text-primary" role="status"></div> Checking availability...';
            
            // Fetch availability
            fetch(`/check-availability?room_id=${roomId}&start_time=${startTime}&end_time=${endTime}&booking_id=${bookingId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.available) {
                        statusElem.innerHTML = '<div class="alert alert-success mb-0 py-2"><i class="fas fa-check-circle me-1"></i> Room is available for the selected time.</div>';
                    } else {
                        statusElem.innerHTML = '<div class="alert alert-danger mb-0 py-2"><i class="fas fa-exclamation-circle me-1"></i> Room is already booked during this time.</div>';
                    }
                    calculateTotal();
                })
                .catch(error => {
                    statusElem.innerHTML = '<div class="alert alert-warning mb-0 py-2"><i class="fas fa-exclamation-triangle me-1"></i> Error checking availability.</div>';
                    console.error('Error checking availability:', error);
                });
        }, 500);
        
        // Attach event listeners
        roomSelect.addEventListener('change', checkRoomAvailability);
        startTimeInput.addEventListener('change', checkRoomAvailability);
        endTimeInput.addEventListener('change', checkRoomAvailability);
        
        // Check availability on page load if all required values are present
        if (roomSelect.value && startTimeInput.value && endTimeInput.value) {
            checkRoomAvailability();
        }
    }
    
    // Set up add-on selection interaction
    const addonItems = document.querySelectorAll('.addon-item');
    addonItems.forEach(item => {
        const checkbox = item.querySelector('.addon-checkbox');
        
        if (checkbox) {
            item.addEventListener('click', function(e) {
                if (e.target !== checkbox && e.target.type !== 'number') {
                    checkbox.checked = !checkbox.checked;
                    item.classList.toggle('selected', checkbox.checked);
                    calculateTotal();
                }
            });
            
            checkbox.addEventListener('change', function() {
                item.classList.toggle('selected', this.checked);
                calculateTotal();
            });
            
            const quantityInput = item.querySelector('.addon-quantity');
            if (quantityInput) {
                quantityInput.addEventListener('change', calculateTotal);
                quantityInput.addEventListener('input', calculateTotal);
            }
        }
    });
    
    // Calculate booking total price
    function calculateTotal() {
        // Only proceed if necessary elements exist
        if (!roomSelect || !startTimeInput || !endTimeInput) return;
        
        const roomId = roomSelect.value;
        const startTime = startTimeInput.value ? new Date(startTimeInput.value) : null;
        const endTime = endTimeInput.value ? new Date(endTimeInput.value) : null;
        const discount = parseFloat(discountInput?.value) || 0;
        
        let roomCharge = 0;
        let addonsCharge = 0;
        let totalPrice = 0;
        
        // Get room pricing
        if (roomId && startTime && endTime && !isNaN(startTime) && !isNaN(endTime)) {
            // Get room rate data from data attributes
            const selectedOption = roomSelect.options[roomSelect.selectedIndex];
            const hourlyRate = parseFloat(selectedOption.dataset.hourlyRate) || 0;
            const halfDayRate = parseFloat(selectedOption.dataset.halfDayRate) || 0;
            const fullDayRate = parseFloat(selectedOption.dataset.fullDayRate) || 0;
            
            // Calculate duration in hours
            const durationHours = (endTime - startTime) / (1000 * 60 * 60);
            
            // Apply appropriate rate based on duration
            if (durationHours <= 4) {
                // Hourly rate
                roomCharge = hourlyRate * durationHours;
            } else if (durationHours <= 6) {
                // Half-day rate
                roomCharge = halfDayRate;
            } else {
                // Full-day rate
                roomCharge = fullDayRate;
            }
        }
        
        // Calculate add-ons charge
        const selectedAddons = document.querySelectorAll('.addon-checkbox:checked');
        selectedAddons.forEach(addon => {
            const addonItem = addon.closest('.addon-item');
            const priceText = addonItem.querySelector('.text-muted.small').textContent;
            const price = parseFloat(priceText.replace('$', ''));
            const quantityInput = addonItem.querySelector('.addon-quantity');
            const quantity = parseInt(quantityInput.value) || 1;
            
            addonsCharge += price * quantity;
        });
        
        // Calculate total
        totalPrice = roomCharge + addonsCharge - discount;
        
        // Update UI
        document.getElementById('roomCharge').textContent = '$' + roomCharge.toFixed(2);
        document.getElementById('addonsCharge').textContent = '$' + addonsCharge.toFixed(2);
        document.getElementById('totalPrice').textContent = '$' + totalPrice.toFixed(2);
        
        // Updated price animation
        const totalPriceElement = document.getElementById('totalPrice');
        totalPriceElement.classList.add('price-updated');
        setTimeout(() => {
            totalPriceElement.classList.remove('price-updated');
        }, 1000);
    }
    
    // Calculate total when discount changes
    if (discountInput) {
        discountInput.addEventListener('input', calculateTotal);
    }
    
    // Calculate total when attendees change (for room capacity warnings)
    if (attendeesInput && roomSelect) {
        attendeesInput.addEventListener('input', function() {
            const attendees = parseInt(attendeesInput.value) || 0;
            const selectedOption = roomSelect.options[roomSelect.selectedIndex];
            const capacity = parseInt(selectedOption.dataset.capacity) || 0;
            
            const capacityWarning = document.getElementById('capacityWarning');
            if (capacityWarning) {
                if (attendees > capacity) {
                    capacityWarning.textContent = `Warning: Exceeds room capacity of ${capacity} people`;
                    capacityWarning.classList.remove('d-none');
                } else {
                    capacityWarning.classList.add('d-none');
                }
            }
            
            calculateTotal();
        });
    }
    
    // Initialize total calculation on page load
    calculateTotal();
}

/**
 * Initialize DataTables with custom configuration
 */
function initializeDataTables() {
    if (typeof $.fn.DataTable !== 'undefined') {
        // Default configuration for all data tables
        const dataTableConfig = {
            responsive: true,
            language: {
                search: '<i class="fas fa-search"></i>',
                searchPlaceholder: 'Search...',
                lengthMenu: 'Show _MENU_ entries',
                info: 'Showing _START_ to _END_ of _TOTAL_ entries',
                infoEmpty: 'Showing 0 to 0 of 0 entries',
                infoFiltered: '(filtered from _MAX_ total entries)',
                zeroRecords: 'No matching records found',
                emptyTable: 'No data available',
                paginate: {
                    first: '<i class="fas fa-angle-double-left"></i>',
                    previous: '<i class="fas fa-angle-left"></i>',
                    next: '<i class="fas fa-angle-right"></i>',
                    last: '<i class="fas fa-angle-double-right"></i>'
                }
            },
            dom: '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>' +
                 '<"row"<"col-sm-12"tr>>' +
                 '<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
            pageLength: 25,
            lengthMenu: [[10, 25, 50, -1], [10, 25, 50, 'All']],
            stateSave: true
        };
        
        // Initialize bookings table
        const bookingsTable = $('#bookingsTable');
        if (bookingsTable.length) {
            bookingsTable.DataTable({
                ...dataTableConfig,
                order: [[3, 'desc']], // Sort by date column
                columnDefs: [
                    { targets: -1, orderable: false } // Disable sorting for actions column
                ]
            });
        }
        
        // Initialize clients table
        const clientsTable = $('#clientsTable');
        if (clientsTable.length) {
            clientsTable.DataTable({
                ...dataTableConfig,
                order: [[0, 'asc']], // Sort by company name
                columnDefs: [
                    { targets: -1, orderable: false } // Disable sorting for actions column
                ]
            });
        }
        
        // Initialize rooms table
        const roomsTable = $('#roomsTable');
        if (roomsTable.length) {
            roomsTable.DataTable({
                ...dataTableConfig,
                order: [[0, 'asc']], // Sort by room name
                columnDefs: [
                    { targets: -1, orderable: false } // Disable sorting for actions column
                ]
            });
        }
        
        // Initialize addons table
        const addonsTable = $('#addonsTable');
        if (addonsTable.length) {
            addonsTable.DataTable({
                ...dataTableConfig,
                order: [[0, 'asc']], // Sort by addon name
                columnDefs: [
                    { targets: -1, orderable: false } // Disable sorting for actions column
                ]
            });
        }
    }
}

/**
 * Initialize dashboard widgets with real-time data and charts
 */
function initializeDashboardWidgets() {
    // Load dashboard data via AJAX
    loadDashboardData();
    
    // Initialize dashboard charts
    initializeBookingsChart();
    initializeRevenueChart();
    initializeOccupancyChart();
    
    // Setup automatic refresh every 5 minutes
    setInterval(loadDashboardData, 5 * 60 * 1000);
    
    // Initialize today's bookings timeline
    initializeTodayTimeline();
    
    // Initialize room status display
    updateRoomStatusDisplay();
}

/**
 * Load dashboard data via AJAX
 */
function loadDashboardData() {
    fetch('/api/dashboard/data')
        .then(response => response.json())
        .then(data => {
            // Update statistics
            updateDashboardStats(data.stats);
            
            // Update upcoming bookings list
            updateUpcomingBookings(data.upcoming_bookings);
            
            // Update today's bookings
            updateTodayBookings(data.today_bookings);
            
            // Update room status
            updateRoomStatus(data.room_status);
        })
        .catch(error => {
            console.error('Error loading dashboard data:', error);
            showToast('Failed to load dashboard data', 'error');
        });
}

/**
 * Update dashboard statistics
 * @param {Object} stats - Dashboard statistics data
 */
function updateDashboardStats(stats) {
    // Update counters with animation
    animateCounter('totalActiveBookings', stats.active_bookings);
    animateCounter('totalClients', stats.total_clients);
    animateCounter('totalRooms', stats.total_rooms);
    animateCounter('todayEvents', stats.today_events);
    
    // Update revenue stats if present
    if (stats.revenue) {
        document.getElementById('monthlyRevenue').textContent = formatCurrency(stats.revenue.monthly);
        document.getElementById('revenueChange').textContent = `${stats.revenue.change}%`;
        
        const revenueChangeElement = document.getElementById('revenueChange');
        if (stats.revenue.change >= 0) {
            revenueChangeElement.classList.add('text-success');
            revenueChangeElement.classList.remove('text-danger');
            revenueChangeElement.innerHTML = `<i class="fas fa-arrow-up me-1"></i>${stats.revenue.change}%`;
        } else {
            revenueChangeElement.classList.add('text-danger');
            revenueChangeElement.classList.remove('text-success');
            revenueChangeElement.innerHTML = `<i class="fas fa-arrow-down me-1"></i>${Math.abs(stats.revenue.change)}%`;
        }
    }
}

/**
 * Animate a counter from current value to new value
 * @param {string} elementId - ID of the element to animate
 * @param {number} newValue - Target value for animation
 */
function animateCounter(elementId, newValue) {
    const counterElement = document.getElementById(elementId);
    if (!counterElement) return;
    
    const currentValue = parseInt(counterElement.textContent) || 0;
    const duration = 1000; // Animation duration in ms
    const stepTime = 50; // Time between steps in ms
    const steps = duration / stepTime;
    const stepValue = (newValue - currentValue) / steps;
    
    let currentStep = 0;
    let currentStepValue = currentValue;
    
    const interval = setInterval(() => {
        currentStep++;
        currentStepValue += stepValue;
        
        if (currentStep >= steps) {
            clearInterval(interval);
            counterElement.textContent = newValue;
        } else {
            counterElement.textContent = Math.round(currentStepValue);
        }
    }, stepTime);
}

/**
 * Initialize booking chart
 */
function initializeBookingsChart() {
    const bookingsChartCanvas = document.getElementById('bookingsChart');
    if (!bookingsChartCanvas) return;
    
    // Fetch booking data for chart
    fetch('/api/reports/bookings-by-month')
        .then(response => response.json())
        .then(data => {
            const ctx = bookingsChartCanvas.getContext('2d');
            
            // Create chart
            window.bookingsChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [
                        {
                            label: 'Confirmed',
                            data: data.confirmed,
                            backgroundColor: '#1cc88a',
                            borderColor: '#1cc88a',
                            borderWidth: 1
                        },
                        {
                            label: 'Tentative',
                            data: data.tentative,
                            backgroundColor: '#f6c23e',
                            borderColor: '#f6c23e',
                            borderWidth: 1
                        },
                        {
                            label: 'Cancelled',
                            data: data.cancelled,
                            backgroundColor: '#e74a3b',
                            borderColor: '#e74a3b',
                            borderWidth: 1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        x: {
                            stacked: true,
                            grid: {
                                display: false
                            }
                        },
                        y: {
                            stacked: true,
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            position: 'top'
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        }
                    }
                }
            });
        })
        .catch(error => {
            console.error('Error loading bookings chart data:', error);
            bookingsChartCanvas.parentNode.innerHTML = '<div class="alert alert-danger">Failed to load chart data</div>';
        });
}

/**
 * Set up real-time updates for active pages
 */
function setupRealTimeUpdates() {
    // Only run on pages that need real-time updates
    const shouldEnableRealTime = document.getElementById('calendar') || 
                               document.getElementById('dashboard-stats') ||
                               document.getElementById('room-status-display');
    
    if (!shouldEnableRealTime) return;
    
    // Poll for updates every minute for dashboard
    if (document.getElementById('dashboard-stats')) {
        setInterval(() => {
            loadDashboardData();
        }, 60000);
    }
    
    // Poll for updates every 2 minutes for calendar
    if (document.getElementById('calendar')) {
        setInterval(() => {
            if (window.bookingCalendar) {
                window.bookingCalendar.refetchEvents();
            }
        }, 120000);
    }
    
    // Poll for room status updates every minute
    if (document.getElementById('room-status-display')) {
        setInterval(() => {
            updateRoomStatusDisplay();
        }, 60000);
    }
}

// ===== UTILITY FUNCTIONS =====

/**
 * Debounce function to limit how often a function can be called
 * @param {Function} func - Function to debounce
 * @param {number} wait - Wait time in milliseconds
 * @returns {Function} - Debounced function
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(context, args), wait);
    };
}

/**
 * Format currency value
 * @param {number} amount - Amount to format
 * @returns {string} - Formatted currency string
 */
function formatCurrency(amount) {
    return new Intl.NumberFormat(SYSTEM.locale, {
        style: 'currency',
        currency: SYSTEM.currency,
        minimumFractionDigits: 2
    }).format(amount);
}

/**
 * Capitalize first letter of a string
 * @param {string} string - String to capitalize
 * @returns {string} - Capitalized string
 */
function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
}

/**
 * Get CSS class for booking status
 * @param {string} status - Booking status
 * @returns {string} - CSS class name
 */
function getStatusClass(status) {
    switch (status) {
        case 'tentative': return 'warning';
        case 'confirmed': return 'success';
        case 'cancelled': return 'danger';
        default: return 'secondary';
    }
}

/**
 * Toggle theme between light and dark
 */
function toggleTheme() {
    const body = document.body;
    const isDarkTheme = body.classList.toggle('dark-theme');
    localStorage.setItem('theme', isDarkTheme ? 'dark' : 'light');
    
    // Update theme color in meta tag for mobile
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    if (themeColorMeta) {
        themeColorMeta.content = isDarkTheme ? '#343a40' : '#4e73df';
    }
}

/**
 * Show toast notification
 * @param {string} message - Notification message
 * @param {string} type - Notification type (success, error, warning, info)
 */
function showToast(message, type = 'info') {
    // Create toast container if it doesn't exist
    let toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    // Create toast element
    const toastId = 'toast-' + Date.now();
    const toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center border-0 bg-${getStatusClass(type)}`;
    toastElement.id = toastId;
    toastElement.setAttribute('role', 'alert');
    toastElement.setAttribute('aria-live', 'assertive');
    toastElement.setAttribute('aria-atomic', 'true');
    
    // Create toast content
    const iconMap = {
        success: 'fas fa-check-circle',
        error: 'fas fa-exclamation-circle',
        warning: 'fas fa-exclamation-triangle',
        info: 'fas fa-info-circle'
    };
    
    const icon = iconMap[type] || iconMap.info;
    
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body text-white">
                <i class="${icon} me-2"></i>${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    // Add toast to container
    toastContainer.appendChild(toastElement);
    
    // Initialize and show toast
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: SYSTEM.toastDuration
    });
    toast.show();
    
    // Play notification sound if available
    if (type in SYSTEM.notificationSounds) {
        SYSTEM.notificationSounds[type].play().catch(e => {
            // Suppress errors from browsers that block autoplay
            console.log('Notification sound blocked by browser policy');
        });
    }
    
    // Remove toast from DOM after hiding
    toastElement.addEventListener('hidden.bs.toast', function() {
        this.remove();
    });
}

/**
 * Setup security features (auto logout, CSRF protection)
 */
function setupSecurityFeatures() {
    // Setup auto logout
    setupAutoLogout();
    
    // Add CSRF token to all AJAX requests
    setupCSRFProtection();
}

/**
 * Setup auto logout after inactivity
 */
function setupAutoLogout() {
    let logoutTimer;
    
    // Function to reset the logout timer
    function resetLogoutTimer() {
        clearTimeout(logoutTimer);
        logoutTimer = setTimeout(showLogoutWarning, SYSTEM.autoLogoutTime);
    }
    
    // Function to show logout warning modal
    function showLogoutWarning() {
        // Create warning modal if it doesn't exist
        let warningModal = document.getElementById('logoutWarningModal');
        if (!warningModal) {
            warningModal = document.createElement('div');
            warningModal.className = 'modal fade';
            warningModal.id = 'logoutWarningModal';
            warningModal.tabIndex = -1;
            warningModal.setAttribute('aria-hidden', 'true');
            
            warningModal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header bg-warning text-white">
                            <h5 class="modal-title"><i class="fas fa-clock me-2"></i>Session Timeout</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p>Your session is about to expire due to inactivity.</p>
                            <div class="d-flex align-items-center justify-content-center my-3">
                                <div class="display-5 fw-bold text-danger" id="logoutCountdown">60</div>
                                <div class="ms-2">seconds</div>
                            </div>
                            <p class="mb-0">Would you like to continue your session?</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-success" id="continueSessionBtn">
                                <i class="fas fa-redo me-2"></i>Continue Session
                            </button>
                            <a href="/logout" class="btn btn-danger">
                                <i class="fas fa-sign-out-alt me-2"></i>Logout Now
                            </a>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(warningModal);
            
            // Setup continue session button
            document.getElementById('continueSessionBtn').addEventListener('click', function() {
                const bsModal = bootstrap.Modal.getInstance(warningModal);
                bsModal.hide();
                resetLogoutTimer();
            });
        }
        
        // Show the modal
        const bsModal = new bootstrap.Modal(warningModal);
        bsModal.show();
        
        // Start countdown
        let countdown = 60;
        const countdownElement = document.getElementById('logoutCountdown');
        const countdownInterval = setInterval(function() {
            countdown--;
            countdownElement.textContent = countdown;
            
            if (countdown <= 0) {
                clearInterval(countdownInterval);
                window.location.href = '/logout';
            }
        }, 1000);
        
        // Reset timer when continuing session
        warningModal.addEventListener('hidden.bs.modal', function() {
            clearInterval(countdownInterval);
        });
    }
    
    // Reset timer on user activity
    const events = ['mousedown', 'keydown', 'mousemove', 'scroll', 'touchstart'];
    events.forEach(function(event) {
        document.addEventListener(event, debounce(resetLogoutTimer, 300), false);
    });
    
    // Initial timer start
    resetLogoutTimer();
}

/**
 * Setup CSRF protection for AJAX requests
 */
function setupCSRFProtection() {
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    
    if (csrfToken) {
        // Add token to all AJAX requests
        document.addEventListener('DOMContentLoaded', function() {
            $.ajaxSetup({
                headers: {
                    'X-CSRFToken': csrfToken
                }
            });
            
            // Add token to fetch requests
            const originalFetch = window.fetch;
            window.fetch = function(url, options = {}) {
                // Only add for same-origin requests
                if (url.startsWith('/') || url.startsWith(window.location.origin)) {
                    options.headers = options.headers || {};
                    options.headers['X-CSRFToken'] = csrfToken;
                }
                return originalFetch(url, options);
            };
        });
    }
}

/**
 * Setup form navigation warnings
 */
function setupFormNavigationWarnings() {
    // Track forms with unsaved changes
    const forms = document.querySelectorAll('form:not(.no-warning)');
    
    forms.forEach(form => {
        let formChanged = false;
        
        // Track form changes
        const inputs = form.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('change', function() {
                formChanged = true;
            });
        });
        
        // Reset on submit
        form.addEventListener('submit', function() {
            formChanged = false;
        });
        
        // Show warning on navigate away
        window.addEventListener('beforeunload', function(event) {
            if (formChanged) {
                const message = 'You have unsaved changes. Are you sure you want to leave?';
                event.returnValue = message;
                return message;
            }
        });
    });
}

/**
 * Setup back to top button
 */
function setupBackToTopButton() {
    // Create back to top button if it doesn't exist
    let backToTopBtn = document.getElementById('backToTopBtn');
    if (!backToTopBtn) {
        backToTopBtn = document.createElement('button');
        backToTopBtn.id = 'backToTopBtn';
        backToTopBtn.className = 'btn btn-primary btn-icon rounded-circle back-to-top';
        backToTopBtn.innerHTML = '<i class="fas fa-arrow-up"></i>';
        backToTopBtn.setAttribute('aria-label', 'Back to top');
        backToTopBtn.style.display = 'none';
        document.body.appendChild(backToTopBtn);
    }
    
    // Show/hide button based on scroll position
    window.addEventListener('scroll', function() {
        if (window.pageYOffset > 300) {
            backToTopBtn.style.display = 'block';
        } else {
            backToTopBtn.style.display = 'none';
        }
    });
    
    // Smooth scroll to top on click
    backToTopBtn.addEventListener('click', function() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    });
}

/**
 * Setup print buttons functionality
 */
function setupPrintButtons() {
    const printButtons = document.querySelectorAll('.btn-print');
    printButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            // If there's a specific target to print
            const targetId = this.getAttribute('data-print-target');
            if (targetId) {
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    // Create a new window with only the target content
                    const printWindow = window.open('', '_blank');
                    printWindow.document.write('<html><head><title>Print</title>');
                    
                    // Add all stylesheets
                    const stylesheets = document.querySelectorAll('link[rel="stylesheet"]');
                    stylesheets.forEach(stylesheet => {
                        printWindow.document.write(stylesheet.outerHTML);
                    });
                    
                    // Add print-specific styles
                    printWindow.document.write('<style>body{padding:20px;} @media print{.no-print{display:none !important;}} .print-header{margin-bottom:20px;}</style>');
                    printWindow.document.write('</head><body>');
                    
                    // Add print header
                    printWindow.document.write(`
                        <div class="print-header">
                            <h2>${document.title}</h2>
                            <p>Printed on ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString()}</p>
                        </div>
                    `);
                    
                    // Add content
                    printWindow.document.write(targetElement.innerHTML);
                    printWindow.document.write('</body></html>');
                    
                    printWindow.document.close();
                    printWindow.focus();
                    
                    // Print after styles are loaded
                    setTimeout(() => {
                        printWindow.print();
                        printWindow.close();
                    }, 1000);
                }
            } else {
                // Print entire window
                window.print();
            }
        });
    });
}

/**
 * Initialize notification system
 */
function initializeNotificationSystem() {
    const notificationBell = document.querySelector('.notification-bell');
    if (!notificationBell) return;
    
    // Fetch notifications
    fetchNotifications();
    
    // Set up notification bell click
    notificationBell.addEventListener('click', function(e) {
        e.preventDefault();
        showNotificationsPanel();
    });
    
    // Periodically check for new notifications
    setInterval(fetchNotifications, 5 * 60 * 1000); // Every 5 minutes
}

/**
 * Fetch user notifications
 */
function fetchNotifications() {
    const notificationBadge = document.querySelector('.notification-badge');
    if (!notificationBadge) return;
    
    fetch('/api/notifications')
        .then(response => response.json())
        .then(data => {
            const count = data.unread_count || 0;
            
            // Update badge
            notificationBadge.textContent = count;
            notificationBadge.style.display = count > 0 ? 'block' : 'none';
            
            // Store notifications for later use
            window.userNotifications = data.notifications || [];
        })
        .catch(error => {
            console.error('Error fetching notifications:', error);
        });
}

/**
 * Show notifications panel
 */
function showNotificationsPanel() {
    // Create or get notifications panel
    let notificationsPanel = document.getElementById('notificationsPanel');
    if (!notificationsPanel) {
        notificationsPanel = document.createElement('div');
        notificationsPanel.id = 'notificationsPanel';
        notificationsPanel.className = 'notifications-panel card shadow';
        document.body.appendChild(notificationsPanel);
    }
    
    // Populate notifications
    const notifications = window.userNotifications || [];
    
    let notificationsHTML = `
        <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
            <h5 class="mb-0"><i class="fas fa-bell me-2"></i>Notifications</h5>
            <button type="button" class="btn-close btn-close-white" id="closeNotificationsBtn" aria-label="Close"></button>
        </div>
        <div class="card-body p-0">
    `;
    
    if (notifications.length > 0) {
        notificationsHTML += '<div class="list-group list-group-flush">';
        
        notifications.forEach(notification => {
            const isUnread = !notification.read;
            const timeAgo = formatTimeAgo(new Date(notification.timestamp));
            
            notificationsHTML += `
                <a href="${notification.url}" class="list-group-item list-group-item-action${isUnread ? ' list-group-item-unread' : ''}" data-id="${notification.id}">
                    <div class="d-flex w-100 justify-content-between">
                        <h6 class="mb-1">${notification.title}</h6>
                        <small>${timeAgo}</small>
                    </div>
                    <p class="mb-1">${notification.message}</p>
                </a>
            `;
        });
        
        notificationsHTML += '</div>';
    } else {
        notificationsHTML += `
            <div class="text-center py-5">
                <i class="fas fa-bell-slash fa-3x text-muted mb-3"></i>
                <p class="mb-0">No new notifications</p>
            </div>
        `;
    }
    
    notificationsHTML += `
        </div>
        <div class="card-footer text-center">
            <a href="/notifications" class="text-primary">View All Notifications</a>
        </div>
    `;
    
    notificationsPanel.innerHTML = notificationsHTML;
    
    // Show panel
    notificationsPanel.classList.add('show');
    
    // Set up close button
    document.getElementById('closeNotificationsBtn').addEventListener('click', function() {
        notificationsPanel.classList.remove('show');
    });
    
    // Set up click outside to close
    document.addEventListener('click', function closePanel(e) {
        if (!notificationsPanel.contains(e.target) && !document.querySelector('.notification-bell').contains(e.target)) {
            notificationsPanel.classList.remove('show');
            document.removeEventListener('click', closePanel);
        }
    });
    
    // Mark notifications as read when clicked
    const notificationItems = notificationsPanel.querySelectorAll('.list-group-item');
    notificationItems.forEach(item => {
        item.addEventListener('click', function() {
            const notificationId = this.getAttribute('data-id');
            markNotificationAsRead(notificationId);
            this.classList.remove('list-group-item-unread');
        });
    });
}

/**
 * Mark notification as read
 * @param {string} id - Notification ID
 */
function markNotificationAsRead(id) {
    fetch(`/api/notifications/${id}/read`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(() => {
        // Update unread count
        const notificationBadge = document.querySelector('.notification-badge');
        if (notificationBadge) {
            const currentCount = parseInt(notificationBadge.textContent) || 0;
            const newCount = Math.max(0, currentCount - 1);
            notificationBadge.textContent = newCount;
            notificationBadge.style.display = newCount > 0 ? 'block' : 'none';
        }
        
        // Update notifications array
        if (window.userNotifications) {
            const notification = window.userNotifications.find(n => n.id === id);
            if (notification) {
                notification.read = true;
            }
        }
    })
    .catch(error => {
        console.error('Error marking notification as read:', error);
    });
}

/**
 * Format time ago from date
 * @param {Date} date - Date to format
 * @returns {string} - Formatted time ago string
 */
function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    let interval = Math.floor(seconds / 31536000);
    if (interval > 1) return interval + ' years ago';
    
    interval = Math.floor(seconds / 2592000);
    if (interval > 1) return interval + ' months ago';
    
    interval = Math.floor(seconds / 86400);
    if (interval > 1) return interval + ' days ago';
    
    interval = Math.floor(seconds / 3600);
    if (interval > 1) return interval + ' hours ago';
    
    interval = Math.floor(seconds / 60);
    if (interval > 1) return interval + ' minutes ago';
    
    return 'just now';
}

// Initialize the system
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        console.log(`${SYSTEM.name} loading...`);
    });
} else {
    console.log(`${SYSTEM.name} loading...`);
}