from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import json
import os
from pydantic import BaseModel
from typing import Optional
import agents

app = FastAPI(title="Multi-Agent RAG Databricks Order Portal")

# CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "orders.db"

class ChatRequest(BaseModel):
    query: str
    api_key: Optional[str] = None
    databricks_host: Optional[str] = None
    databricks_path: Optional[str] = None
    databricks_token: Optional[str] = None

# --- Dual Database Helper ---

def get_db_config(request: Request):
    """
    Extracts Databricks configuration from request headers
    """
    host = request.headers.get("x-databricks-host")
    path = request.headers.get("x-databricks-path")
    token = request.headers.get("x-databricks-token")
    if host and path and token:
        return {
            "server_hostname": host,
            "http_path": path,
            "access_token": token
        }
    return None

def execute_query(request: Request, sql: str, params=None):
    if params is None:
        params = ()
        
    db_config = get_db_config(request)
    
    # Route to Databricks SQL if config headers exist
    if db_config:
        try:
            from databricks import sql as dbsql
            conn = dbsql.connect(
                server_hostname=db_config["server_hostname"],
                http_path=db_config["http_path"],
                access_token=db_config["access_token"]
            )
            cursor = conn.cursor()
            
            # Format parameters (Databricks connector uses %s instead of ?)
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
            raise HTTPException(status_code=500, detail="databricks-sql-connector package not installed on server. Run 'pip install databricks-sql-connector'.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Databricks SQL Error: {str(e)}")
            
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
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
def startup_event():
    if not os.path.exists(DB_FILE):
        print("Local database orders.db not found. Seeding database automatically...")
        try:
            import db
            db.generate_data()
            print("Database seeded successfully.")
        except Exception as e:
            print(f"Error seeding database: {str(e)}")

@app.get("/api/orders")
def get_orders(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    status: Optional[str] = None
):
    query_str = "SELECT id, order_id, customer_name, email, order_date, status, total_amount, city FROM orders WHERE 1=1"
    count_str = "SELECT COUNT(*) as count FROM orders WHERE 1=1"
    params = []
    
    if search:
        search_filter = " AND (customer_name LIKE ? OR order_id LIKE ? OR email LIKE ? OR city LIKE ?)"
        query_str += search_filter
        count_str += search_filter
        term = f"%{search}%"
        params.extend([term, term, term, term])
        
    if status:
        status_filter = " AND status = ?"
        query_str += status_filter
        count_str += status_filter
        params.append(status)
        
    # Count total records matching filters
    count_res = execute_query(request, count_str, params)
    total_records = count_res[0]["count"] if count_res else 0
    
    # Add ordering and pagination
    query_str += " ORDER BY order_date DESC LIMIT ? OFFSET ?"
    offset = (page - 1) * limit
    params_with_paging = list(params) + [limit, offset]
    
    rows = execute_query(request, query_str, params_with_paging)
    orders = [dict(r) for r in rows]
    
    total_pages = (total_records + limit - 1) // limit
    
    return {
        "orders": orders,
        "pagination": {
            "total_records": total_records,
            "total_pages": total_pages,
            "current_page": page,
            "limit": limit
        }
    }

@app.get("/api/orders/{order_id}")
def get_order_by_id(request: Request, order_id: str):
    rows = execute_query(request, "SELECT * FROM orders WHERE order_id = ?", (order_id.upper(),))
    
    if not rows:
        raise HTTPException(status_code=404, detail="Order not found")
        
    order = dict(rows[0])
    # Parse items JSON
    try:
        if isinstance(order["items"], str):
            order["items"] = json.loads(order["items"])
    except:
        order["items"] = []
    return order

@app.get("/api/analytics")
def get_analytics(request: Request):
    # 1. Total Metrics
    totals = execute_query(request, "SELECT COUNT(*) as total_count, ROUND(SUM(total_amount), 2) as total_sales FROM orders")
    totals_dict = totals[0] if totals else {"total_count": 0, "total_sales": 0.0}
    
    # 2. Status Breakdown
    status_rows = execute_query(request, "SELECT status, COUNT(*) as count, ROUND(SUM(total_amount), 2) as sales FROM orders GROUP BY status")
    
    # 3. Category distribution (loads last 1000 orders to sample)
    recent_items_rows = execute_query(request, "SELECT items, total_amount FROM orders ORDER BY order_date DESC LIMIT 1000")
    
    cat_distribution = {}
    for row in recent_items_rows:
        try:
            items_val = row["items"]
            items_list = json.loads(items_val) if isinstance(items_val, str) else items_val
            for item in items_list:
                cat = item.get("category", "Other")
                sales = item.get("price", 0) * item.get("quantity", 1)
                cat_distribution[cat] = cat_distribution.get(cat, 0.0) + sales
        except:
            pass
            
    category_sales = [{"category": k, "sales": round(v, 2)} for k, v in cat_distribution.items()]
    
    # 4. Daily sales volume for the last 30 days (date format-compatible)
    daily_rows = execute_query(request, """
        SELECT date(order_date) as day, 
               COUNT(*) as count, 
               ROUND(SUM(total_amount), 2) as sales 
        FROM orders 
        GROUP BY day 
        ORDER BY day DESC 
        LIMIT 30
    """)
    daily_sales = [dict(r) for r in daily_rows]
    daily_sales.reverse()
    
    return {
        "summary": {
            "total_orders": totals_dict["total_count"],
            "total_sales": totals_dict["total_sales"] or 0.0
        },
        "status_breakdown": status_rows,
        "category_sales": category_sales,
        "daily_sales": daily_sales
    }

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    POST SSE stream endpoint. Integrates optional Databricks connection configurations.
    """
    def event_generator():
        try:
            databricks_config = None
            if request.databricks_host:
                databricks_config = {
                    "server_hostname": request.databricks_host,
                    "http_path": request.databricks_path,
                    "access_token": request.databricks_token
                }
            
            # Get generator from agents engine
            gen = agents.run_query(request.query, request.api_key, databricks_config)
            for chunk in gen:
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            err = {"type": "error", "content": str(e)}
            yield f"data: {json.dumps(err)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Serve frontend static files
os.makedirs("static", exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
