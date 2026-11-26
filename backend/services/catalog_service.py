from sqlalchemy import text

from src.decisionos.data.extract import get_engine

MAX_PAGE_SIZE = 100
MAX_PRODUCT_ID = 2**31 - 1  # PostgreSQL integer
MAX_OFFSET = 2**31 - 1


def list_products(*, search=None, category=None, department=None, limit=50, offset=0):
    if not 1 <= limit <= MAX_PAGE_SIZE or not 0 <= offset <= MAX_OFFSET:
        raise ValueError("Invalid product pagination.")

    conditions = []
    params = {"limit": limit, "offset": offset}
    exact_id_match = "FALSE"
    if search and (term := search.strip()):
        match = "strpos(lower(item_id), lower(:search)) > 0"
        params["search"] = term
        digits = term.lstrip("0")
        if term.isascii() and term.isdecimal() and 0 < len(digits) <= 10:
            product_id = int(digits)
            if product_id <= MAX_PRODUCT_ID:
                match += " OR id = :product_id"
                exact_id_match = "id = :product_id"
                params["product_id"] = product_id
        conditions.append(f"({match})")
    if category is not None:
        conditions.append("category = :category")
        params["category"] = category
    if department is not None:
        conditions.append("department = :department")
        params["department"] = department
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = text(f"""
        WITH matching AS (
            SELECT id AS product_id, item_id, category, department, {exact_id_match} AS exact_id_match
            FROM products
            {where}
        ), page AS (
            SELECT * FROM matching
            ORDER BY exact_id_match DESC, item_id, product_id
            LIMIT :limit OFFSET :offset
        )
        SELECT page.product_id, page.item_id, page.category, page.department, totals.total
        FROM (SELECT COUNT(*) AS total FROM matching) totals
        LEFT JOIN page ON TRUE
        ORDER BY page.exact_id_match DESC, page.item_id, page.product_id
    """)
    with get_engine().connect() as connection:
        rows = connection.execute(query, params).mappings().all()
    products = [
        {key: value for key, value in row.items() if key != "total"}
        for row in rows if row["product_id"] is not None
    ]
    return {"products": products, "total": rows[0]["total"], "limit": limit, "offset": offset}


def list_stores(*, state=None):
    query = text("""
        SELECT id AS store_id, store_id AS store_code, state
        FROM stores
        WHERE (CAST(:state AS text) IS NULL OR state = :state)
        ORDER BY store_code, id
    """)
    with get_engine().connect() as connection:
        rows = connection.execute(query, {"state": state}).mappings().all()
    return [dict(row) for row in rows]


def list_categories():
    query = text("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category")
    with get_engine().connect() as connection:
        return connection.execute(query).scalars().all()


def list_departments(*, category=None):
    query = text("""
        SELECT DISTINCT department FROM products
        WHERE department IS NOT NULL AND (CAST(:category AS text) IS NULL OR category = :category)
        ORDER BY department
    """)
    with get_engine().connect() as connection:
        return connection.execute(query, {"category": category}).scalars().all()


def list_states():
    query = text("SELECT DISTINCT state FROM stores WHERE state IS NOT NULL ORDER BY state")
    with get_engine().connect() as connection:
        return connection.execute(query).scalars().all()
