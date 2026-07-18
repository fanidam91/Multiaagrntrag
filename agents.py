import sqlite3
import json
import re
import time
from google import genai
from google.genai import types

DB_FILE = "orders.db"

# Global context for Databricks credentials
DATABRICKS_CONTEXT = {}

def execute_select(sql: str, params=None):
    if params is None:
        params = ()
    clean_sql = sql.strip().lower()
    if not clean_sql.startswith("select"):
        return {"error": "Only SELECT queries are allowed."}
    
    # Check for write keywords
    forbidden = ["insert", "update", "delete", "drop", "alter", "create", "replace", "truncate", "vacuum", "pragma"]
    for word in forbidden:
        if re.search(r'\b' + word + r'\b', clean_sql):
            return {"error": f"Modifying query keyword '{word}' is not allowed."}

    # If Databricks is configured in context, route to Databricks SQL
    db_config = DATABRICKS_CONTEXT.get("config")
    if db_config and db_config.get("server_hostname"):
        try:
            from databricks import sql as dbsql
            conn = dbsql.connect(
                server_hostname=db_config["server_hostname"],
                http_path=db_config["http_path"],
                access_token=db_config["access_token"]
            )
            cursor = conn.cursor()
            
            # Format params for Databricks SQL connector (uses %s instead of ?)
            if params:
                formatted_sql = sql.replace("?", "%s")
                cursor.execute(formatted_sql, params)
            else:
                cursor.execute(sql)
            
            columns = [desc[0] for desc in cursor.description]
            result = []
            for row in cursor.fetchall():
                result.append(dict(zip(columns, row)))
                
            cursor.close()
            conn.close()
            return result
        except ImportError:
            return {"error": "databricks-sql-connector package is not installed. Run 'pip install databricks-sql-connector' to enable Databricks support."}
        except Exception as e:
            return {"error": f"Databricks SQL Error: {str(e)}"}

    # Default to local SQLite
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        result = [dict(r) for r in rows]
        conn.close()
        return result
    except Exception as e:
        return {"error": str(e)}

# --- AGENT TOOLS ---

def get_order_details(order_id: str) -> str:
    """Retrieve full details of a specific order by its Order ID (e.g. ORD-1025 or 1025)."""
    order_id = order_id.upper().strip()
    if not order_id.startswith("ORD-"):
        order_id = f"ORD-{order_id}"
    
    rows = execute_select("SELECT * FROM orders WHERE order_id = ?", (order_id,))
    if isinstance(rows, dict) and "error" in rows:
        return f"Error executing query: {rows['error']}"
    if not rows:
        # Fallback check for numbers in the order_id
        match = re.search(r'\d+', order_id)
        if match:
            num = match.group()
            fuzzy_rows = execute_select("SELECT * FROM orders WHERE order_id LIKE ?", (f"%{num}%",))
            if fuzzy_rows and not isinstance(fuzzy_rows, dict):
                return json.dumps(fuzzy_rows[0], indent=2)
        return f"Order {order_id} was not found in the database."
    
    order = rows[0]
    # Parse items JSON to make it readable
    try:
        order["items"] = json.loads(order["items"])
    except:
        pass
    return json.dumps(order, indent=2)

def search_orders(query_str: str) -> str:
    """Search for orders matching a customer name, email, city, or containing specific items. Returns up to 10 matching orders."""
    sql = """
    SELECT order_id, customer_name, email, order_date, status, total_amount, city, carrier 
    FROM orders 
    WHERE customer_name LIKE ? 
       OR email LIKE ? 
       OR city LIKE ?
       OR items LIKE ?
    ORDER BY order_date DESC
    LIMIT 10
    """
    param = f"%{query_str}%"
    rows = execute_select(sql, (param, param, param, param))
    if isinstance(rows, dict) and "error" in rows:
        return f"Error executing query: {rows['error']}"
    if not rows:
        return f"No orders found matching search query: '{query_str}'."
    return json.dumps(rows, indent=2)

def get_analytics_summary() -> str:
    """Get overall orders metrics: total revenue, order count, and a breakdown of count and sales by status."""
    count_sql = "SELECT COUNT(*) as total_orders, ROUND(SUM(total_amount), 2) as total_revenue FROM orders"
    status_sql = "SELECT status, COUNT(*) as count, ROUND(SUM(total_amount), 2) as sales FROM orders GROUP BY status"
    
    stats = execute_select(count_sql)
    status_breakdown = execute_select(status_sql)
    
    if (isinstance(stats, dict) and "error" in stats) or (isinstance(status_breakdown, dict) and "error" in status_breakdown):
        return "Error loading analytics summaries."
        
    summary = {
        "overall": stats[0] if stats else {"total_orders": 0, "total_revenue": 0.0},
        "status_distribution": status_breakdown
    }
    return json.dumps(summary, indent=2)

def run_read_only_sql_query(sql: str) -> str:
    """Run a custom read-only SQL query on the orders database. Useful for complex queries, filters, counts, sums, or items counts."""
    # Ensure read-only SELECT
    rows = execute_select(sql)
    if isinstance(rows, dict) and "error" in rows:
        return f"SQL Error: {rows['error']}"
    return json.dumps(rows[:30], indent=2)  # Cap at 30 rows for prompt safety

# --- MULTI-AGENT EXECUTION STREAM ---

def run_agent_fallback(user_query: str):
    """
    Intelligent local rule-based system that simulates Agent thinking and yields SSE chunks.
    Allows project to run perfectly without an API Key.
    """
    yield {"type": "thought", "content": "Routing Agent: Analyzing query intent..."}
    time.sleep(0.4)
    
    q_lower = user_query.lower()
    
    # 1. Order ID Details Lookup
    order_id_match = re.search(r'\b(ord-)?\d{4,5}\b', q_lower)
    if order_id_match:
        raw_id = order_id_match.group()
        norm_id = raw_id.upper()
        if not norm_id.startswith("ORD-"):
            norm_id = f"ORD-{norm_id}"
            
        yield {"type": "thought", "content": f"Router: Query classified as 'Order Detail Lookup'.\nActivating Order Retrieval Agent for order: {norm_id}"}
        time.sleep(0.6)
        
        yield {"type": "thought", "content": f"Order Retrieval Agent: Querying database for order details..."}
        details_str = get_order_details(norm_id)
        time.sleep(0.5)
        
        if "not found" in details_str:
            yield {"type": "thought", "content": f"Order Retrieval Agent: Order not found. Attempting search on customer name..."}
            time.sleep(0.5)
            yield {"type": "thought", "content": f"Support Agent: Preparing help response."}
            final_text = f"I searched the database for order ID **{norm_id}**, but I couldn't find a match. Could you please double check your order number? It should be in the format `ORD-XXXX` (between ORD-1001 and ORD-6000)."
        else:
            order_data = json.loads(details_str)
            yield {"type": "thought", "content": f"Order Retrieval Agent: Details retrieved successfully.\nSupport Agent: Formatting order tracking timeline."}
            time.sleep(0.5)
            
            # Format custom response
            items_desc = "\n".join([f"- {item['quantity']}x {item['name']} (${item['price']})" for item in order_data['items']])
            final_text = f"### Order Details for **{order_data['order_id']}**\n\n"
            final_text += f"- **Customer Name**: {order_data['customer_name']}\n"
            final_text += f"- **Status**: `{order_data['status']}`\n"
            final_text += f"- **Total Amount**: ${order_data['total_amount']:.2f}\n"
            final_text += f"- **Order Date**: {order_data['order_date']}\n"
            if order_data['carrier']:
                final_text += f"- **Shipping Carrier**: {order_data['carrier']}\n"
                final_text += f"- **Tracking Number**: `{order_data['tracking_number']}`\n"
                final_text += f"- **Estimated Delivery**: {order_data['estimated_delivery']}\n"
            final_text += f"- **Shipping Address**: {order_data['shipping_address']}, {order_data['city']}, {order_data['zip_code']}\n\n"
            final_text += f"**Items Ordered**:\n{items_desc}\n\n"
            final_text += f"**Order History logs**:\n```\n{order_data['support_notes']}\n```"
            
        for word in final_text.split(" "):
            yield {"type": "text", "content": word + " "}
            time.sleep(0.02)
        return

    # 2. Analytics Check
    analytics_keywords = ["how many", "revenue", "sales", "average", "stats", "analytics", "breakdown", "summary", "in progress", "shipped", "pending"]
    if any(kw in q_lower for kw in analytics_keywords):
        yield {"type": "thought", "content": "Router: Query classified as 'Analytics/Aggregate Report'.\nActivating Database Analytics Agent..."}
        time.sleep(0.6)
        
        yield {"type": "thought", "content": "Analytics Agent: Fetching overall database statistics and breakdown..."}
        stats_data = json.loads(get_analytics_summary())
        time.sleep(0.5)
        
        # Specific query matching to make response relevant
        if "revenue" in q_lower or "sales" in q_lower:
            total_rev = stats_data["overall"]["total_revenue"]
            yield {"type": "thought", "content": f"Analytics Agent: Calculating total revenue..."}
            time.sleep(0.3)
            final_text = f"### Revenue Report\n\n- **Total Revenue**: ${total_rev:,.2f}\n- **Total Orders**: {stats_data['overall']['total_orders']:,}\n\nHere is a sales breakdown by order status:\n\n| Status | Count | Total Sales |\n|---|---|---|\n"
            for row in stats_data["status_distribution"]:
                final_text += f"| {row['status']} | {row['count']:,} | ${row['sales']:,.2f} |\n"
                
        elif "in progress" in q_lower or "processing" in q_lower:
            processing_row = next((r for r in stats_data["status_distribution"] if r["status"] == "Processing"), {"count": 0})
            yield {"type": "thought", "content": "Analytics Agent: Querying count of 'Processing' orders..."}
            time.sleep(0.3)
            final_text = f"There are currently **{processing_row['count']:,}** orders in **Processing** status (in progress). You can see the full distribution of order statuses in the Data Dashboard on the right panel!"
            
        else:
            final_text = f"### System Order Analytics Summary\n\n- **Total Orders**: {stats_data['overall']['total_orders']:,}\n- **Total Gross Sales**: ${stats_data['overall']['total_revenue']:,.2f}\n\n**Status Distribution**:\n\n"
            for row in stats_data["status_distribution"]:
                final_text += f"- **{row['status']}**: {row['count']:,} orders (${row['sales']:,.2f} sales)\n"
                
        yield {"type": "thought", "content": "Support Agent: Generating analytics summary response."}
        time.sleep(0.4)
        for word in final_text.split(" "):
            yield {"type": "text", "content": word + " "}
            time.sleep(0.02)
        return

    # 3. Customer Search by Name / Email
    yield {"type": "thought", "content": "Router: Query classified as 'Customer Name/Item search'.\nActivating Order Retrieval Agent..."}
    time.sleep(0.5)
    
    yield {"type": "thought", "content": f"Order Retrieval Agent: Searching database for terms: '{user_query}'..."}
    search_res = search_orders(user_query)
    time.sleep(0.6)
    
    if "No orders found" in search_res:
        yield {"type": "thought", "content": "Order Retrieval Agent: No records found. Support Agent routing to general greeting."}
        time.sleep(0.4)
        final_text = f"Hello! I am your Multi-Agent Order Assistant. I can help you search through our **5,000 active orders** database.\n\nTry asking me questions like:\n- *What is the status of order ORD-1250?*\n- *How many orders are in progress?*\n- *What is the total revenue of shipped orders?*\n- *Find orders for customer 'John'*"
    else:
        results = json.loads(search_res)
        yield {"type": "thought", "content": f"Order Retrieval Agent: Found {len(results)} matches.\nSupport Agent: Formulating search results table."}
        time.sleep(0.4)
        final_text = f"I found the following orders matching **'{user_query}'**:\n\n| Order ID | Customer Name | Date | Status | Amount | City |\n|---|---|---|---|---|---|\n"
        for r in results:
            final_text += f"| **{r['order_id']}** | {r['customer_name']} | {r['order_date'][:10]} | `{r['status']}` | ${r['total_amount']:.2f} | {r['city']} |\n"
        final_text += f"\n*Click on any order ID in the dashboard table to view its full shipping logs and product list.*"

    for word in final_text.split(" "):
        yield {"type": "text", "content": word + " "}
        time.sleep(0.02)

def run_agent_gemini(user_query: str, api_key: str):
    """
    Executes the multi-agent system using Google GenAI with live tool routing
    and streams thoughts & final response to the UI.
    """
    try:
        client = genai.Client(api_key=api_key)
        
        # Tools map for execution
        tool_map = {
            "get_order_details": get_order_details,
            "search_orders": search_orders,
            "get_analytics_summary": get_analytics_summary,
            "run_read_only_sql_query": run_read_only_sql_query
        }
        
        # Build prompt
        prompt = f"""You are a helpful Multi-Agent RAG Orchestrator managing a retail orders database.
You have access to 5,000 orders.
Your goal is to answer the customer's query: "{user_query}"

Rules:
1. Route queries appropriately:
   - For specific Order IDs (like ORD-1025), use `get_order_details`.
   - For finding customers by name, email or item search, use `search_orders`.
   - For general aggregate statistics, use `get_analytics_summary`.
   - For custom complex logic, filterings, counts, or questions that can't be answered by the above, write a safe `SELECT` query using `run_read_only_sql_query`.
2. Present tables and timelines clearly in Markdown.
3. Keep response professional and structured.
"""
        yield {"type": "thought", "content": "Routing Agent: Activating Gemini Model and preparing agent loop..."}
        
        # Run conversation loop for tool calls
        # We start by sending the user query
        chat_contents = [prompt]
        
        agent_loop_limit = 5
        loop_count = 0
        
        while loop_count < agent_loop_limit:
            loop_count += 1
            
            # Request content from model
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=chat_contents,
                config=types.GenerateContentConfig(
                    tools=[get_order_details, search_orders, get_analytics_summary, run_read_only_sql_query],
                    temperature=0.0
                )
            )
            
            # Check if there are function calls
            function_calls = response.function_calls
            
            if not function_calls:
                # No more tool calls! We can stream the final text response.
                # Since the response text is already generated, we will stream it word-by-word or use stream API
                # But wait, since we did generate_content, we have the text. Let's yield it.
                yield {"type": "thought", "content": "Support Agent: Finalizing response..."}
                text = response.text or ""
                for word in text.split(" "):
                    yield {"type": "text", "content": word + " "}
                    time.sleep(0.01)
                return
            
            # Execute tool calls
            for call in function_calls:
                name = call.name
                args = call.args
                call_id = call.id
                
                yield {"type": "thought", "content": f"Router Agent: Calling tool '{name}' with arguments: {json.dumps(args)}"}
                time.sleep(0.5)
                
                # Execute
                tool_func = tool_map.get(name)
                if not tool_func:
                    result = f"Error: Tool {name} not found."
                else:
                    try:
                        # Unpack arguments
                        result = tool_func(**args)
                    except Exception as ex:
                        result = f"Error executing tool: {str(ex)}"
                        
                yield {"type": "thought", "content": f"Database Agent: Tool output received. Length: {len(result)} bytes."}
                time.sleep(0.3)
                
                # Update chat history with model's function call response and the function result
                # Note: google-genai SDK expects us to send the history back
                # To feed function results back, we append the response object (containing function call) 
                # and a part containing function response.
                chat_contents.append(response)
                
                # Create a Part with FunctionResponse
                func_resp_part = types.Part.from_function_response(
                    name=name,
                    response={"result": result}
                )
                
                # Wrap it in Content
                content_obj = types.Content(role="user", parts=[func_resp_part])
                chat_contents.append(content_obj)
                
        yield {"type": "thought", "content": "Agent Loop exceeded limit. Support Agent taking over."}
        yield {"type": "text", "content": "I apologize, but my agent system took too many cycles to complete this request. Could you simplify your query?"}
        
    except Exception as e:
        yield {"type": "error", "content": f"Error running Gemini Agent: {str(e)}. Falling back to Local Agent."}
        time.sleep(1.0)
        yield from run_agent_fallback(user_query)

def run_query(user_query: str, api_key: str = None, databricks_config: dict = None):
    """
    Main entry point. If api_key is present, use Gemini agent, else use fallback.
    """
    DATABRICKS_CONTEXT["config"] = databricks_config
    if api_key and len(api_key.strip()) > 10:
        return run_agent_gemini(user_query, api_key)
    else:
        return run_agent_fallback(user_query)
