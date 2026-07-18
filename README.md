# Multi-Agent RAG Operations Portal on Azure Databricks

A production-grade, highly aesthetic **Multi-Agent RAG (Retrieval-Augmented Generation) Chatbot** and **Operational Dashboard** designed to query, search, and analyze **10,500 retail orders** natively inside **Azure Databricks** or locally.

---

## 📸 Interface Preview
The portal features a split-pane layout:
* **Left Pane**: Real-time Chatbot with streaming agent steps (representing router, database search, analytics, and support agents executing behind the scenes).
* **Right Pane**: Tabbed dashboard containing:
  * **Analytics Dashboard**: Operational metrics cards and dynamic visual charts (Chart.js status doughnut, category sales bar, and daily sales line graphs).
  * **Database Explorer**: Debounced data-table containing all transactions, complete with an itemized product list and historical timeline logs.

---

## 🚀 Key Features

* **Azure Databricks Routing**: Connect the local web app directly to an **Azure Databricks SQL Warehouse** (via the settings cog) to execute agent queries natively on your cloud Delta Tables.
* **Spark Structured Streaming Ingestion**: Native Databricks ingestion pipelines (`readStream` / `writeStream`) showing real-time CSV drop files appended into Delta tables with checkpoints.
* **Specialized Agent Nodes**:
  * **Router Agent**: Analyzes intent and routes queries to relevant nodes.
  * **Retrieval Agent**: Natively searches individual order records by ID or wildcards.
  * **Analytics Agent**: Computes statistical summaries (revenue totals, status breakdowns).
  * **Support Agent**: Handles general inquiries and drafts shipping logs/responses.
* **Gemini LLM Tool-Use**: Supports live tool calling using the Gemini API, with a smart local NLP rule engine fallback if no API key is set.

---

## 📂 Project Structure

```
├── static/                   # Frontend assets
│   ├── index.html            # Main dashboard HTML
│   ├── style.css             # Premium glassmorphism styling
│   └── app.js                # SSE streaming connection reader
├── agents.py                 # Multi-Agent routing logic & tools
├── main.py                   # FastAPI backend server
├── db.py                     # 500-order local dataset generator
├── orders.csv                # Generated local spreadsheet dataset
├── databricks_notebook.ipynb # Native Azure Databricks Jupyter Notebook
├── databricks_ddl.sql        # Delta table creation DDL script
└── README.md                 # Project documentation
```

---

## 🛠️ Local Installation & Setup

1. **Install Dependencies**:
   Ensure you have Python 3.11+ installed. Run:
   ```bash
   pip install fastapi uvicorn faker pandas google-genai
   ```

2. **Generate Local Database**:
   Build the mock 500 orders database and export the CSV file:
   ```bash
   python db.py
   ```

3. **Launch the Server**:
   Start the FastAPI app locally:
   ```bash
   python main.py
   ```
   Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your web browser.

---

## ☁️ Azure Databricks Deployment

1. **Import the Notebook**:
   * Open your Azure Databricks workspace.
   * Go to **Workspace** -> **Users** -> **[Your User]** -> Right-click -> **Import** -> **File**.
   * Upload `databricks_notebook.ipynb`.

2. **Create target Catalog Table**:
   Run the following schema definition in your Databricks SQL Warehouse editor:
   ```sql
   CREATE TABLE IF NOT EXISTS adb_core_data_dev_aue.default.orders (
       id BIGINT GENERATED ALWAYS AS IDENTITY,
       order_id STRING NOT NULL,
       customer_name STRING NOT NULL,
       email STRING NOT NULL,
       phone STRING NOT NULL,
       order_date TIMESTAMP NOT NULL,
       status STRING NOT NULL,
       total_amount DOUBLE NOT NULL,
       shipping_address STRING NOT NULL,
       city STRING NOT NULL,
       zip_code STRING NOT NULL,
       country STRING NOT NULL,
       carrier STRING,
       tracking_number STRING,
       estimated_delivery DATE,
       items STRING NOT NULL,
       support_notes STRING
   )
   USING delta;
   ```

3. **Run Ingestion and Streams**:
   Attach the notebook to your running cluster and run all cells:
   * It will load a seed of 500 orders.
   * It starts a background Spark Structured Stream monitoring `/tmp/orders_raw/`.
   * It drops two CSV batches (**5,000 + 5,000 orders**) to demonstrate real-time streaming updates, bringing the total table count to **10,500**.
