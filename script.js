function updateEmployeeCharts() {
    if (typeof Chart === "undefined") return;

    const departmentCanvas = document.getElementById("departmentChart");
    const statusCanvas = document.getElementById("employeeStatusChart");

    const counts = {};

    allEmployees.forEach(employee => {
        const department = employee.department || "Unknown";
        counts[department] = (counts[department] || 0) + 1;
    });

    // offsetParent is null when the canvas is hidden (its section is display:none)
    if (departmentCanvas && departmentCanvas.offsetParent !== null) {
        if (departmentChart) departmentChart.destroy();

        departmentChart = new Chart(departmentCanvas, {
            type: "doughnut",
            data: {
                labels: Object.keys(counts),
                datasets: [{ data: Object.values(counts), backgroundColor: CHART_COLORS }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    const active = allEmployees.filter(e => e.status === "Active").length;
    const inactive = allEmployees.length - active;

    if (statusCanvas && statusCanvas.offsetParent !== null) {
        if (employeeStatusChart) employeeStatusChart.destroy();

        employeeStatusChart = new Chart(statusCanvas, {
            type: "pie",
            data: {
                labels: ["Active", "Inactive"],
                datasets: [{ data: [active, inactive], backgroundColor: ["#22c55e", "#94a3b8"] }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }
}

function updateAttendanceChart(present, absent, leave) {
    if (typeof Chart === "undefined") return;

    const canvas = document.getElementById("attendanceChart");
    if (!canvas || canvas.offsetParent === null) return;

    if (attendanceChart) attendanceChart.destroy();

    attendanceChart = new Chart(canvas, {
        type: "bar",
        data: {
            labels: ["Present", "Absent", "Leave"],
            datasets: [{
                label: "Attendance Records",
                data: [present, absent, leave],
                backgroundColor: ["#22c55e", "#ef4444", "#f59e0b"]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
        }
    });
}