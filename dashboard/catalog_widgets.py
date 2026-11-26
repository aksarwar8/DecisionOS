import requests
import streamlit as st

from dashboard import api_client

PAGE_SIZE = 50
CATALOG_TTL_SECONDS = 120


@st.cache_data(ttl=CATALOG_TTL_SECONDS, max_entries=128, show_spinner=False)
def _catalog_data(resource, **params):
    fetch = {
        "categories": api_client.get_catalog_categories,
        "departments": api_client.get_catalog_departments,
        "products": api_client.get_catalog_products,
        "states": api_client.get_catalog_states,
        "stores": api_client.get_catalog_stores,
    }
    return fetch[resource](**params)


def select_product_scope(prefix: str) -> tuple[str | None, str | None]:
    categories = _catalog_data("categories")["categories"]
    category = st.selectbox("Category", [None, *categories], key=f"{prefix}_category",
                            format_func=lambda value: value if value is not None else "All categories")
    departments = _catalog_data("departments", category=category)["departments"]
    department_key = f"{prefix}_department"
    if st.session_state.get(department_key) not in departments:
        st.session_state.pop(department_key, None)
    department = st.selectbox(
        "Department", [None, *departments], key=department_key,
        format_func=lambda value: value if value is not None else "All departments",
    )
    return category, department


def select_product(prefix: str) -> int | None:
    category, department = select_product_scope(prefix)
    search = st.text_input("Search products", placeholder="Item code or product ID",
                           max_chars=100, key=f"{prefix}_search").strip()
    filters = (category, department, search)
    filters_key = f"{prefix}_filters"
    offset_key = f"{prefix}_offset"
    selection_key = f"{prefix}_product"
    if st.session_state.get(filters_key) != filters:
        st.session_state[filters_key] = filters
        st.session_state[offset_key] = 0
        st.session_state.pop(selection_key, None)
    offset = st.session_state.get(offset_key, 0)
    page = _catalog_data(
        "products", search=search or None, category=category, department=department,
        limit=PAGE_SIZE, offset=offset,
    )
    products = {entry["product_id"]: entry["item_id"] for entry in page["products"]}
    if st.session_state.get(selection_key) not in products:
        st.session_state.pop(selection_key, None)

    if products:
        st.caption(f"Showing {offset + 1}–{offset + len(products)} of {page['total']:,} products")
    else:
        st.info("No products on this page. Try a different filter or go to the previous page.")

    if offset or page["total"] > PAGE_SIZE:
        previous, following = st.columns(2)
        previous.button(
            "Previous", key=f"{prefix}_previous", disabled=offset == 0,
            on_click=_change_page, args=(offset_key, selection_key, max(0, offset - PAGE_SIZE)),
        )
        following.button(
            "Next", key=f"{prefix}_next", disabled=offset + PAGE_SIZE >= page["total"],
            on_click=_change_page, args=(offset_key, selection_key, offset + PAGE_SIZE),
        )
    return st.selectbox(
        "Product", list(products), index=None, format_func=products.__getitem__,
        key=selection_key, disabled=not products, placeholder="Select an item code",
    )


def _change_page(offset_key, selection_key, offset):
    st.session_state[offset_key] = offset
    st.session_state.pop(selection_key, None)


def select_store_scope(
    prefix: str, *, placeholder="All matching stores",
) -> tuple[str | None, int | None]:
    states = _catalog_data("states")["states"]
    state = st.selectbox("State", [None, *states], key=f"{prefix}_state",
                         format_func=lambda value: value if value is not None else "All states")
    stores = {
        entry["store_id"]: entry["store_code"]
        for entry in _catalog_data("stores", state=state)
    }
    selection_key = f"{prefix}_store"
    if st.session_state.get(selection_key) not in stores:
        st.session_state.pop(selection_key, None)
    if not stores:
        st.info("No stores match the selected state.")
    store_id = st.selectbox(
        "Store", list(stores), index=None, format_func=stores.__getitem__,
        key=selection_key, disabled=not stores, placeholder=placeholder,
    )
    return state, store_id


def select_store(prefix: str) -> int | None:
    return select_store_scope(prefix, placeholder="Select a store code")[1]


def catalog_selection(prefix: str) -> tuple[int | None, int | None]:
    products, stores = st.columns(2)
    try:
        with products:
            product_id = select_product(prefix)
        with stores:
            store_id = select_store(prefix)
    except (requests.RequestException, ValueError):
        st.error("The catalog could not be loaded. Check the DecisionOS API and rerun the page.")
        return None, None
    return product_id, store_id
