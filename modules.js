// ========================================
// LEAVE, PAYROLL, USERS AND EMPLOYEE DASHBOARD
// (loads after script.js and shares its helpers)
// ========================================

const LEAVE_URL = API_BASE + "leaves/";
const PAYROLL_URL = API_BASE + "payroll/";
const USERS_URL = API_BASE + "users/";

let allLeaves = [];
let allPayroll = [];
let allUsers = [];
let payslipModal = null;
let currentPayslip = null;


function errorRow(columns, message) {
    return `<tr><td colspan="${columns}" class="text-center text-danger">${escapeHTML(message)}</td></tr>`;
}

function emptyRow(columns, message) {
    return `<tr><td colspan="${columns}" class="text-center">${escapeHTML(message)}</td></tr>`;
}


// ========================================
// 1. EMPLOYEE DASHBOARD (profile + check in / out)
// ========================================

function renderMyProfile() {
    if (ROLE !== "Employee") return;

    const me = allEmployees[0];

    if (!me) {
        setHTML("myProfileBody", "No employee record is linked to your login.");
        return;
    }

    const rows = [
        ["Name", me.name], ["Email", me.email], ["Phone", me.phone],
        ["Department", me.department], ["Designation", me.designation],
        ["Joined", me.joining_date], ["Status", me.status]
    ];

    setHTML("myProfileBody", rows.map(([label, value]) =>
        `<div class="profile-row"><span>${label}</span><strong>${escapeHTML(value)}</strong></div>`
    ).join(""));

    setText("todayDate", new Date().toLocaleDateString("en-IN", {
        weekday: "long", day: "numeric", month: "long"
    }));

    const record = allAttendance.find(item => item.date === todayString());
    let message = "You have not checked in yet.";

    if (record) {
        if (record.status === "Leave") {
            message = "You are on approved leave today.";
        } else if (record.check_in && record.check_out) {
            message = `Checked in at ${formatTime(record.check_in)} and out at ${formatTime(record.check_out)}.`;
        } else if (record.check_in) {
            message = `Checked in at ${formatTime(record.check_in)}.`;
        } else {
            message = `Marked ${record.status} by HR.`;
        }
    }

    setHTML("todayStatus", `<div class="today-box">${escapeHTML(message)}</div>`);

    const checkIn = document.getElementById("checkInBtn");
    const checkOut = document.getElementById("checkOutBtn");

    if (checkIn) checkIn.disabled = !!(record && (record.check_in || record.status === "Leave"));
    if (checkOut) checkOut.disabled = !(record && record.check_in && !record.check_out);
}

async function checkIn() {
    try {
        await apiRequest(ATTENDANCE_API_URL + "check-in/", "POST", {});
        await loadData();
    } catch (error) {
        alert(error.message);
    }
}

async function checkOut() {
    try {
        await apiRequest(ATTENDANCE_API_URL + "check-out/", "POST", {});
        await loadData();
    } catch (error) {
        alert(error.message);
    }
}


// ========================================
// 2. LEAVE
// ========================================

function leaveBadge(status) {
    if (status === "Approved") return "bg-success";
    if (status === "Rejected") return "bg-danger";
    return "bg-warning text-dark";
}

async function loadLeaves() {
    try {
        allLeaves = getRecords(await apiRequest(LEAVE_URL));
        displayLeaves();
    } catch (error) {
        setHTML("leaveTableBody", errorRow(9, error.message));
    }
}

function displayLeaves() {
    const table = document.getElementById("leaveTableBody");
    if (!table) return;

    const wanted = document.getElementById("leaveFilterStatus")?.value || "";
    const list = allLeaves.filter(item => !wanted || item.status === wanted);

    if (list.length === 0) {
        table.innerHTML = emptyRow(9, "No leave requests found.");
        return;
    }

    table.innerHTML = list.map(item => {
        let actions = "";

        if (item.status === "Pending" && IS_STAFF) {
            actions = `
                <button class="btn btn-sm btn-success" type="button" onclick="reviewLeave(${Number(item.id)}, 'approve')">Approve</button>
                <button class="btn btn-sm btn-danger" type="button" onclick="reviewLeave(${Number(item.id)}, 'reject')">Reject</button>`;
        } else if (item.status === "Pending") {
            actions = `<button class="btn btn-sm btn-secondary" type="button" onclick="cancelLeave(${Number(item.id)})">Cancel</button>`;
        }

        return `
            <tr>
                <td>${escapeHTML(item.employee_name)}</td>
                <td>${escapeHTML(item.leave_type)}</td>
                <td>${escapeHTML(item.start_date)}</td>
                <td>${escapeHTML(item.end_date)}</td>
                <td>${escapeHTML(item.days)}</td>
                <td>${escapeHTML(item.reason || "-")}</td>
                <td><span class="badge ${leaveBadge(item.status)}">${escapeHTML(item.status)}</span></td>
                <td>${escapeHTML(item.remarks || "-")}</td>
                <td>${actions}</td>
            </tr>`;
    }).join("");
}

async function reviewLeave(id, action) {
    const remarks = prompt(
        action === "approve" ? "Remarks (optional):" : "Reason for rejecting (optional):",
        ""
    );

    if (remarks === null) return;

    try {
        await apiRequest(`${LEAVE_URL}${id}/${action}/`, "POST", { remarks });
        await loadLeaves();
        await loadData();
    } catch (error) {
        alert(error.message);
    }
}

async function cancelLeave(id) {
    if (!confirm("Cancel this leave request?")) return;

    try {
        await apiRequest(`${LEAVE_URL}${id}/`, "DELETE");
        await loadLeaves();
    } catch (error) {
        alert(error.message);
    }
}

function initializeLeaveForm() {
    const form = document.getElementById("leaveForm");
    if (!form) return;

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const start = document.getElementById("leaveStart").value;
        const end = document.getElementById("leaveEnd").value;

        if (end < start) {
            alert("The end date cannot be before the start date.");
            return;
        }

        try {
            await apiRequest(LEAVE_URL, "POST", {
                leave_type: document.getElementById("leaveType").value,
                start_date: start,
                end_date: end,
                reason: document.getElementById("leaveReason").value.trim()
            });

            alert("Leave request sent to HR.");
            form.reset();
            await loadLeaves();

        } catch (error) {
            alert(error.message);
        }
    });

    document.getElementById("leaveFilterStatus")?.addEventListener("change", displayLeaves);
}


// ========================================
// 3. PAYROLL
// ========================================

function monthLabel(month) {
    const [year, number] = String(month).split("-").map(Number);

    return new Date(year, number - 1, 1)
        .toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

async function loadPayroll() {
    const month = document.getElementById("payrollMonth")?.value || "";

    try {
        allPayroll = getRecords(await apiRequest(PAYROLL_URL + (month ? `?month=${month}` : "")));
        displayPayroll();
    } catch (error) {
        setHTML("payrollTableBody", errorRow(10, error.message));
    }
}

function displayPayroll() {
    const table = document.getElementById("payrollTableBody");
    if (!table) return;

    if (allPayroll.length === 0) {
        table.innerHTML = emptyRow(10, "No payslips found.");
        return;
    }

    table.innerHTML = allPayroll.map(item => `
        <tr>
            <td>${escapeHTML(item.employee_name)}</td>
            <td>${escapeHTML(monthLabel(item.month))}</td>
            <td>${escapeHTML(item.working_days)}</td>
            <td>${escapeHTML(item.present_days)}</td>
            <td>${escapeHTML(item.absent_days)}</td>
            <td>${escapeHTML(item.leave_days)}</td>
            <td>${escapeHTML(item.unpaid_leave_days)}</td>
            <td>${escapeHTML(formatMoney(item.deduction))}</td>
            <td><strong>${escapeHTML(formatMoney(item.net_pay))}</strong></td>
            <td>
                <button class="btn btn-sm btn-info" type="button" title="View payslip"
                        onclick="viewPayslip(${Number(item.id)})">
                    <i class="fa-solid fa-file-invoice"></i>
                </button>
            </td>
        </tr>`).join("");
}

async function generatePayroll() {
    const month = document.getElementById("payrollMonth")?.value || "";

    if (!month) {
        alert("Choose a month first.");
        return;
    }

    if (!confirm(`Generate payroll for ${monthLabel(month)}? Existing payslips for that month will be updated.`)) {
        return;
    }

    try {
        const result = await apiRequest(PAYROLL_URL + "generate/", "POST", { month });
        alert(result.message);
        await loadPayroll();
    } catch (error) {
        alert(error.message);
    }
}

function clearPayrollMonth() {
    const input = document.getElementById("payrollMonth");
    if (input) input.value = "";
    loadPayroll();
}

function payslipHTML(item) {
    const deductionDays = Number(item.absent_days) + Number(item.unpaid_leave_days);
    const perDay = item.working_days ? Number(item.base_salary) / item.working_days : 0;

    return `
        <div class="payslip">
            <h4>Payslip - ${escapeHTML(monthLabel(item.month))}</h4>
            <div class="sub">${escapeHTML(item.employee_name)} | ${escapeHTML(item.employee_designation)}, ${escapeHTML(item.employee_department)}</div>
            <table>
                <tr><td>Employee email</td><td>${escapeHTML(item.employee_email)}</td></tr>
                <tr><td>Working days (Mon-Fri)</td><td>${escapeHTML(item.working_days)}</td></tr>
                <tr><td>Present / Absent / Leave</td><td>${escapeHTML(item.present_days)} / ${escapeHTML(item.absent_days)} / ${escapeHTML(item.leave_days)}</td></tr>
                <tr><td>Unpaid leave days</td><td>${escapeHTML(item.unpaid_leave_days)}</td></tr>
                <tr><td>Monthly salary</td><td>${escapeHTML(formatMoney(item.base_salary))}</td></tr>
                <tr><td>Deduction (${deductionDays} day(s) x ${escapeHTML(formatMoney(perDay))})</td><td>- ${escapeHTML(formatMoney(item.deduction))}</td></tr>
                <tr class="net"><td>Net pay</td><td>${escapeHTML(formatMoney(item.net_pay))}</td></tr>
            </table>
        </div>`;
}

function viewPayslip(id) {
    const item = allPayroll.find(row => Number(row.id) === Number(id));
    if (!item || !payslipModal) return;

    currentPayslip = item;
    setHTML("payslipBody", payslipHTML(item));
    payslipModal.show();
}

function printPayslip() {
    if (!currentPayslip) return;

    const win = window.open("", "_blank", "width=700,height=800");

    if (!win) {
        alert("Please allow pop-ups to print the payslip.");
        return;
    }

    win.document.write(`<!DOCTYPE html><html><head><title>Payslip</title><style>
        body{font-family:Arial,sans-serif;padding:30px;color:#1e293b}
        h4{text-align:center;margin-bottom:4px}.sub{text-align:center;color:#64748b;margin-bottom:20px}
        table{width:100%;border-collapse:collapse}td{padding:9px 0;border-bottom:1px solid #e2e8f0}
        td:last-child{text-align:right}.net td{font-weight:bold;font-size:18px;border-top:2px solid #172554;border-bottom:0}
        </style></head><body>${payslipHTML(currentPayslip)}</body></html>`);

    win.document.close();
    win.focus();
    win.print();
}


// ========================================
// 4. USERS AND ROLES (Admin only)
// ========================================

async function loadUsers() {
    try {
        const [users, employees] = await Promise.all([
            apiRequest(USERS_URL),
            apiRequest(API_URL)
        ]);

        allUsers = Array.isArray(users) ? users : [];
        allEmployees = getRecords(employees);

        displayUsers();
        fillUserEmployeeOptions();

    } catch (error) {
        setHTML("userTableBody", errorRow(4, error.message));
    }
}

function displayUsers() {
    const table = document.getElementById("userTableBody");
    if (!table) return;

    if (allUsers.length === 0) {
        table.innerHTML = emptyRow(4, "No users found.");
        return;
    }

    table.innerHTML = allUsers.map(user => {
        const protectedUser = user.role === "Admin";

        return `
            <tr>
                <td>${escapeHTML(user.username)}</td>
                <td><span class="badge ${protectedUser ? "bg-danger" : user.role === "HR" ? "bg-primary" : "bg-secondary"}">${escapeHTML(user.role)}</span></td>
                <td>${escapeHTML(user.employee_name || "-")}</td>
                <td>${protectedUser ? "" : `
                    <button class="btn btn-sm btn-danger" type="button" title="Delete login"
                            onclick="deleteUser(${Number(user.id)})">
                        <i class="fa-solid fa-trash"></i>
                    </button>`}</td>
            </tr>`;
    }).join("");
}

function fillUserEmployeeOptions() {
    const select = document.getElementById("userEmployee");
    if (!select) return;

    const free = allEmployees.filter(employee => !employee.has_login);

    select.innerHTML = `<option value="">- none -</option>` +
        free.map(employee =>
            `<option value="${Number(employee.id)}">${escapeHTML(employee.name)} (${escapeHTML(employee.email)})</option>`
        ).join("");
}

async function deleteUser(id) {
    if (!confirm("Delete this login? The employee record is kept.")) return;

    try {
        await apiRequest(`${USERS_URL}${id}/`, "DELETE");
        await loadUsers();
    } catch (error) {
        alert(error.message);
    }
}

function initializeUserForm() {
    const form = document.getElementById("userForm");
    if (!form) return;

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const button = form.querySelector("button[type='submit']");
        if (button.disabled) return;          // ignore a double click

        const role = document.getElementById("userRole").value;
        const employee = document.getElementById("userEmployee").value;

        if (role === "Employee" && !employee) {
            alert("Choose the employee this login belongs to.");
            return;
        }

        button.disabled = true;

        try {
            await apiRequest(USERS_URL, "POST", {
                username: document.getElementById("userName").value.trim(),
                password: document.getElementById("userPassword").value,
                role,
                employee: employee ? Number(employee) : null
            });

            alert("Login created.");
            form.reset();
            await loadUsers();

        } catch (error) {
            alert(error.message);
        } finally {
            button.disabled = false;
        }
    });
}


// ========================================
// 5. PAGE LOADING AND STARTUP
// ========================================

function loadSectionExtras(sectionId) {
    if (sectionId === "leaveSection") loadLeaves();
    else if (sectionId === "payrollSection") loadPayroll();
    else if (sectionId === "usersSection" && ROLE === "Admin") loadUsers();
}

document.addEventListener("DOMContentLoaded", function () {
    const payslipElement = document.getElementById("payslipModal");

    if (typeof bootstrap !== "undefined" && payslipElement) {
        payslipModal = new bootstrap.Modal(payslipElement);
    }

    initializeLeaveForm();
    initializeUserForm();

    document.getElementById("payrollMonth")?.addEventListener("change", loadPayroll);
});