// ========================================
// ADMIN LOGIN
// ========================================

const LOGIN_URL = "/api/login/";

// Already logged in? Go straight to the dashboard.
if (localStorage.getItem("authToken") && localStorage.getItem("role")) {
    window.location.replace("index.html");
}

const loginForm = document.getElementById("loginForm");
const messageBox = document.getElementById("message");

function showMessage(text, isError) {
    messageBox.textContent = text;
    messageBox.style.color = isError ? "#fca5a5" : "#86efac";
}

loginForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const button = loginForm.querySelector("button[type='submit']");

    if (!username || !password) {
        showMessage("Please enter username and password.", true);
        return;
    }

    button.disabled = true;
    showMessage("Signing in...", false);

    try {
        // No Authorization header here on purpose.
        const response = await fetch(LOGIN_URL, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json().catch(() => ({}));

        if (response.ok && data.token) {
            localStorage.setItem("authToken", data.token);
            localStorage.setItem("role", data.role || "");
            localStorage.setItem("username", data.username || "");
            localStorage.setItem("employee_id", data.employee_id || "");
            localStorage.setItem("employee_name", data.employee_name || "");
            showMessage("Login successful. Redirecting...", false);
            window.location.replace("index.html");
            return;
        }

        showMessage(data.message || "Invalid username or password.", true);

    } catch (error) {
        showMessage(
            "Cannot reach the server. Make sure Django is running at http://127.0.0.1:8000",
            true
        );
    } finally {
        button.disabled = false;
    }
});