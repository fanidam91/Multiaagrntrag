// --- State variables ---
let apiKey = localStorage.getItem("gemini_api_key") || "";
let dbHost = localStorage.getItem("db_host") || "";
let dbPath = localStorage.getItem("db_path") || "";
let dbToken = localStorage.getItem("db_token") || "";

let currentTab = "analytics";
let currentPage = 1;
let totalPages = 1;
let searchQuery = "";
let statusFilter = "";

// Chart instances
let statusChartInst = null;
let categoryChartInst = null;
let salesLineChartInst = null;

// --- Initialize App ---
document.addEventListener("DOMContentLoaded", () => {
    updateSettingsUI();
    fetchAnalytics();
    fetchOrders();
});

// --- Settings Management (LLM & Databricks) ---
function updateSettingsUI() {
    const statusText = document.getElementById("keyStatusText");
    const indicator = document.getElementById("apiKeyStatus");
    
    document.getElementById("geminiKeyInput").value = apiKey;
    document.getElementById("dbHostInput").value = dbHost;
    document.getElementById("dbPathInput").value = dbPath;
    document.getElementById("dbTokenInput").value = dbToken;
    
    let activeNodes = [];
    if (apiKey) activeNodes.push("Gemini AI");
    if (dbHost) activeNodes.push("Databricks SQL");
    
    if (activeNodes.length > 0) {
        statusText.innerText = activeNodes.join(" & ") + " Active";
        indicator.classList.add("active");
    } else {
        statusText.innerText = "No Credentials (Local Demo)";
        indicator.classList.remove("active");
    }
}

function toggleApiKeyModal() {
    const modal = document.getElementById("apiKeyModal");
    modal.classList.toggle("active");
}

function saveSettings() {
    apiKey = document.getElementById("geminiKeyInput").value.trim();
    dbHost = document.getElementById("dbHostInput").value.trim();
    dbPath = document.getElementById("dbPathInput").value.trim();
    dbToken = document.getElementById("dbTokenInput").value.trim();
    
    if (apiKey) localStorage.setItem("gemini_api_key", apiKey);
    else localStorage.removeItem("gemini_api_key");
    
    if (dbHost) localStorage.setItem("db_host", dbHost);
    else localStorage.removeItem("db_host");
    
    if (dbPath) localStorage.setItem("db_path", dbPath);
    else localStorage.removeItem("db_path");
    
    if (dbToken) localStorage.setItem("db_token", dbToken);
    else localStorage.removeItem("db_token");
    
    updateSettingsUI();
    toggleApiKeyModal();
    
    // Refresh UI & tables
    fetchAnalytics();
    fetchOrders();
    
    let msg = "Portal connection settings saved: ";
    msg += apiKey ? "[Gemini Orchestration: ON] " : "[Gemini Orchestration: OFF (Local NLP)] ";
    msg += dbHost ? "[Database: Databricks SQL Warehouse]" : "[Database: Local orders.db]";
    appendSystemMessage(msg);
}

// --- Tab Switching ---
function switchTab(tabName) {
    currentTab = tabName;
    
    // Toggle active classes on tab buttons
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach(tab => {
        if (tab.getAttribute("onclick").includes(tabName)) {
            tab.classList.add("active");
        } else {
            tab.classList.remove("active");
        }
    });
    
    // Toggle active tab content
    document.getElementById("analyticsTab").classList.toggle("active", tabName === "analytics");
    document.getElementById("explorerTab").classList.toggle("active", tabName === "explorer");
}

// --- Fetch Analytics Dashboard Data ---
async function fetchAnalytics() {
    try {
        const headers = {};
        if (dbHost && dbPath && dbToken) {
            headers["x-databricks-host"] = dbHost;
            headers["x-databricks-path"] = dbPath;
            headers["x-databricks-token"] = dbToken;
        }
        const response = await fetch("/api/analytics", { headers });
        if (!response.ok) throw new Error("Failed to fetch analytics");
        const data = await response.json();
        
        // Populate Metric Cards
        document.getElementById("metricTotalOrders").innerText = Number(data.summary.total_orders).toLocaleString();
        document.getElementById("metricTotalSales").innerText = "$" + Number(data.summary.total_sales).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        
        // Find Processing count
        const proc = data.status_breakdown.find(s => s.status === "Processing")?.count || 0;
        document.getElementById("metricProcessingOrders").innerText = Number(proc).toLocaleString();
        
        // Find Delivered count
        const deliv = data.status_breakdown.find(s => s.status === "Delivered")?.count || 0;
        document.getElementById("metricDeliveredOrders").innerText = Number(deliv).toLocaleString();
        
        // Render Charts
        renderStatusChart(data.status_breakdown);
        renderCategoryChart(data.category_sales);
        renderSalesLineChart(data.daily_sales);
        
    } catch (err) {
        console.error("Analytics Error:", err);
    }
}

// Chart.js renderers
function renderStatusChart(statusData) {
    const ctx = document.getElementById("statusChart").getContext("2d");
    if (statusChartInst) statusChartInst.destroy();
    
    const labels = statusData.map(d => d.status);
    const counts = statusData.map(d => d.count);
    
    statusChartInst = new Chart(ctx, {
        type: "doughnut",
        data: {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: [
                    "#f59e0b", // Pending
                    "#3b82f6", // Processing
                    "#8b5cf6", // Shipped
                    "#10b981", // Delivered
                    "#f43f5e", // Cancelled
                    "#9ca3af"  // Refunded
                ],
                borderWidth: 1,
                borderColor: "rgba(9, 13, 24, 0.4)"
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "right",
                    labels: { color: "#f3f4f6", font: { size: 11, family: "Inter" } }
                }
            }
        }
    });
}

function renderCategoryChart(categoryData) {
    const ctx = document.getElementById("categoryChart").getContext("2d");
    if (categoryChartInst) categoryChartInst.destroy();
    
    // Sort categories by sales
    categoryData.sort((a,b) => b.sales - a.sales);
    
    const labels = categoryData.map(d => d.category);
    const sales = categoryData.map(d => d.sales);
    
    categoryChartInst = new Chart(ctx, {
        type: "bar",
        data: {
            labels: labels,
            datasets: [{
                label: "Sales ($)",
                data: sales,
                backgroundColor: "rgba(99, 102, 241, 0.65)",
                borderColor: "#6366f1",
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#9ca3af" } },
                y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#9ca3af" } }
            }
        }
    });
}

function renderSalesLineChart(dailyData) {
    const ctx = document.getElementById("salesLineChart").getContext("2d");
    if (salesLineChartInst) salesLineChartInst.destroy();
    
    const labels = dailyData.map(d => d.day);
    const sales = dailyData.map(d => d.sales);
    
    salesLineChartInst = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [{
                label: "Daily Sales ($)",
                data: sales,
                borderColor: "#10b981",
                backgroundColor: "rgba(16, 185, 129, 0.08)",
                fill: true,
                tension: 0.35,
                borderWidth: 2,
                pointRadius: 2,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { grid: { display: false }, ticks: { color: "#9ca3af", maxTicksLimit: 10 } },
                y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#9ca3af" } }
            }
        }
    });
}

// --- Fetch Database Explorer Table Data ---
async function fetchOrders() {
    try {
        let url = `/api/orders?page=${currentPage}&limit=50`;
        if (searchQuery) url += `&search=${encodeURIComponent(searchQuery)}`;
        if (statusFilter) url += `&status=${encodeURIComponent(statusFilter)}`;
        
        const headers = {};
        if (dbHost && dbPath && dbToken) {
            headers["x-databricks-host"] = dbHost;
            headers["x-databricks-path"] = dbPath;
            headers["x-databricks-token"] = dbToken;
        }
        const response = await fetch(url, { headers });
        if (!response.ok) throw new Error("Failed to fetch orders list");
        const data = await response.json();
        
        totalPages = data.pagination.total_pages;
        currentPage = data.pagination.current_page;
        
        renderOrdersTable(data.orders);
        updatePaginationUI(data.pagination);
    } catch (err) {
        console.error("Fetch Orders Error:", err);
    }
}

function renderOrdersTable(orders) {
    const tbody = document.getElementById("ordersTableBody");
    tbody.innerHTML = "";
    
    if (orders.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 30px;">No matching order records found in DB.</td></tr>`;
        return;
    }
    
    orders.forEach(o => {
        const tr = document.createElement("tr");
        tr.onclick = () => openOrderDetails(o.order_id);
        
        const statusClass = o.status ? o.status.toLowerCase() : "pending";
        const dateStr = o.order_date ? String(o.order_date).substring(0, 16) : "";
        const totalVal = typeof o.total_amount === 'number' ? o.total_amount.toFixed(2) : '0.00';
        
        tr.innerHTML = `
            <td><strong style="color: var(--accent-indigo)">${o.order_id || ""}</strong></td>
            <td>${o.customer_name || ""}</td>
            <td>${dateStr}</td>
            <td><span class="badge ${statusClass}">${o.status || "Pending"}</span></td>
            <td><strong>$${totalVal}</strong></td>
            <td>${o.city || ""}</td>
        `;
        tbody.appendChild(tr);
    });
}

function updatePaginationUI(p) {
    const info = document.getElementById("paginationInfo");
    const start = p.total_records === 0 ? 0 : (p.current_page - 1) * p.limit + 1;
    const end = Math.min(p.current_page * p.limit, p.total_records);
    
    info.innerText = `Showing ${start}-${end} of ${p.total_records.toLocaleString()} orders`;
    
    document.getElementById("prevPageBtn").disabled = p.current_page <= 1;
    document.getElementById("nextPageBtn").disabled = p.current_page >= p.total_pages;
}

function changePage(direction) {
    const newPage = currentPage + direction;
    if (newPage >= 1 && newPage <= totalPages) {
        currentPage = newPage;
        fetchOrders();
    }
}

// Handle filters
let filterTimeout = null;
function handleSearchFilterChange() {
    // Debounce search input to prevent rapid api querying
    clearTimeout(filterTimeout);
    filterTimeout = setTimeout(() => {
        searchQuery = document.getElementById("dbSearchInput").value.trim();
        statusFilter = document.getElementById("dbStatusFilter").value;
        currentPage = 1;
        fetchOrders();
    }, 300);
}

// --- Order Details Modal ---
async function openOrderDetails(orderId) {
    try {
        const headers = {};
        if (dbHost && dbPath && dbToken) {
            headers["x-databricks-host"] = dbHost;
            headers["x-databricks-path"] = dbPath;
            headers["x-databricks-token"] = dbToken;
        }
        const response = await fetch(`/api/orders/${orderId}`, { headers });
        if (!response.ok) throw new Error("Could not find order details");
        const order = await response.json();
        
        document.getElementById("modalOrderId").innerText = order.order_id;
        document.getElementById("detailName").innerText = order.customer_name;
        document.getElementById("detailEmail").innerText = order.email;
        document.getElementById("detailPhone").innerText = order.phone;
        document.getElementById("detailAddress").innerText = `${order.shipping_address}, ${order.city}, ${order.zip_code}, ${order.country}`;
        document.getElementById("detailCarrier").innerText = order.carrier || "Not dispatched yet";
        document.getElementById("detailTracking").innerText = order.tracking_number || "N/A";
        document.getElementById("detailEstDelivery").innerText = order.estimated_delivery || "Calculating...";
        document.getElementById("detailTotal").innerText = "$" + Number(order.total_amount).toFixed(2);
        
        // Render Items table
        const itemsBody = document.getElementById("detailItemsBody");
        itemsBody.innerHTML = "";
        order.items.forEach(item => {
            const tr = document.createElement("tr");
            const subtotal = item.price * item.quantity;
            tr.innerHTML = `
                <td><span class="code-text" style="background: rgba(99, 102, 241, 0.1); color: var(--accent-indigo)">${item.category}</span></td>
                <td>${item.name}</td>
                <td>$${item.price.toFixed(2)}</td>
                <td>${item.quantity}</td>
                <td><strong>$${subtotal.toFixed(2)}</strong></td>
            `;
            itemsBody.appendChild(tr);
        });
        
        // Render timeline notes
        const timeline = document.getElementById("detailTimeline");
        timeline.innerHTML = "";
        const lines = order.support_notes.split("\n");
        lines.forEach(line => {
            if (!line.trim()) return;
            const div = document.createElement("div");
            div.className = "timeline-item";
            
            // Format log elements (highlight dates)
            const formatted = line.replace(/^\[(.*?)\]/, '<span style="color: var(--accent-indigo)">[$1]</span>');
            div.innerHTML = formatted;
            timeline.appendChild(div);
        });
        
        document.getElementById("orderDetailsModal").classList.add("active");
    } catch (err) {
        alert("Error loading details: " + err.message);
    }
}

function closeDetailsModal() {
    document.getElementById("orderDetailsModal").classList.remove("active");
}

// --- Chat Form & Streaming Engine ---
async function handleChatSubmit(event) {
    event.preventDefault();
    const input = document.getElementById("userInput");
    const text = input.value.trim();
    if (!text) return;
    
    input.value = "";
    appendUserMessage(text);
    
    // Set up agent loading/streaming container
    const messageId = "msg-" + Date.now();
    const messageContainer = appendAgentMessageSkeleton(messageId);
    const messageTextDiv = document.getElementById(`${messageId}-text`);
    const thoughtsDiv = document.getElementById(`${messageId}-thoughts`);
    const thoughtsContainer = document.getElementById(`${messageId}-thoughts-container`);
    
    let accumulatedText = "";
    let accumulatedThoughts = "";
    
    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                query: text, 
                api_key: apiKey,
                databricks_host: dbHost,
                databricks_path: dbPath,
                databricks_token: dbToken
            })
        });
        
        if (!response.ok) throw new Error("Chat engine failed to connect");
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            
            // Save the last line (might be incomplete) back to buffer
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const jsonStr = line.substring(6);
                    try {
                        const chunk = JSON.parse(jsonStr);
                        
                        if (chunk.type === "thought") {
                            // Show thoughts block
                            thoughtsContainer.classList.remove("collapsed");
                            thoughtsContainer.style.display = "block";
                            accumulatedThoughts += chunk.content + "\n";
                            thoughtsDiv.innerText = accumulatedThoughts;
                            thoughtsDiv.scrollTop = thoughtsDiv.scrollHeight;
                        } 
                        else if (chunk.type === "text") {
                            accumulatedText += chunk.content;
                            // Parse markdown live
                            messageTextDiv.innerHTML = marked.parse(accumulatedText);
                        } 
                        else if (chunk.type === "error") {
                            accumulatedText += `\n\n*(Error: ${chunk.content})*`;
                            messageTextDiv.innerHTML = marked.parse(accumulatedText);
                        }
                        
                        // Scroll to bottom
                        const chatThread = document.getElementById("chatThread");
                        chatThread.scrollTop = chatThread.scrollHeight;
                        
                    } catch (e) {
                        console.error("Failed to parse SSE JSON:", e);
                    }
                }
            }
        }
        
        // After stream is finished, refresh dashboard analytics in case DB state changed
        fetchAnalytics();
        
    } catch (err) {
        console.error("Stream Error:", err);
        messageTextDiv.innerHTML = `<p style="color: var(--accent-rose)">Sorry, I encountered an error connecting to the agent engine: ${err.message}</p>`;
    }
}

// --- DOM Appenders ---
function appendUserMessage(text) {
    const thread = document.getElementById("chatThread");
    const msg = document.createElement("div");
    msg.className = "chat-message user";
    msg.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-body">
            <div class="message-sender">You</div>
            <div class="message-text">${escapeHtml(text)}</div>
        </div>
    `;
    thread.appendChild(msg);
    thread.scrollTop = thread.scrollHeight;
}

function appendAgentMessageSkeleton(id) {
    const thread = document.getElementById("chatThread");
    const msg = document.createElement("div");
    msg.className = "chat-message agent";
    msg.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-body" style="width: 100%">
            <div class="message-sender">Agent System</div>
            
            <!-- Collapsible Run Log (Thoughts Console) -->
            <div class="thought-container collapsed" id="${id}-thoughts-container" style="display: none;">
                <div class="thought-header" onclick="toggleThoughtCollapse('${id}')">
                    <span>⚡ Run History & Agent Steps</span>
                    <span class="thought-toggle-icon">▼</span>
                </div>
                <div class="thought-body" id="${id}-thoughts"></div>
            </div>
            
            <!-- Streamed output -->
            <div class="message-text" id="${id}-text">
                <span class="status-label" style="display:flex; align-items:center; gap:8px;">
                    <span class="status-indicator live"></span> Orchestrating agent nodes...
                </span>
            </div>
        </div>
    `;
    thread.appendChild(msg);
    thread.scrollTop = thread.scrollHeight;
    return msg;
}

function toggleThoughtCollapse(id) {
    const container = document.getElementById(`${id}-thoughts-container`);
    container.classList.toggle("collapsed");
}

function appendSystemMessage(text) {
    const thread = document.getElementById("chatThread");
    const msg = document.createElement("div");
    msg.style.cssText = "align-self: center; font-size: 11px; color: var(--accent-indigo); background: rgba(99, 102, 241, 0.08); padding: 6px 16px; border-radius: 20px; border: 1px solid rgba(99, 102, 241, 0.15); animation: slideUp 0.3s ease;";
    msg.innerText = `⚙️ ${text}`;
    thread.appendChild(msg);
    thread.scrollTop = thread.scrollHeight;
}

function escapeHtml(unsafe) {
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
