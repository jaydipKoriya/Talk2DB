import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

from talk2db.config import DEFAULT_DB_URI, DEFAULT_MODEL
from talk2db.security.encryption import CredentialVault
from talk2db.database.connection import DatabaseConnectionManager
from talk2db.database.inspector import CatalogInspector
from talk2db.database.executor import SandboxedExecutor
from talk2db.schema_pruning.indexer import SchemaVectorIndex
from talk2db.agent.graph import create_sql_agent_graph
from langchain.chat_models import init_chat_model

st.set_page_config(
    page_title="Talk2DB",
    page_icon="🔍",
    layout="wide",
)

if "vault" not in st.session_state:
    st.session_state.vault = CredentialVault()

if "conn_mgr" not in st.session_state:
    st.session_state.conn_mgr = None

if "catalog" not in st.session_state:
    st.session_state.catalog = None

if "vector_index" not in st.session_state:
    st.session_state.vector_index = None

if "agent_graph" not in st.session_state:
    st.session_state.agent_graph = None


def disconnect_db():
    if st.session_state.conn_mgr:
        st.session_state.conn_mgr.dispose()
        st.session_state.conn_mgr = None
    st.session_state.catalog = None
    st.session_state.vector_index = None
    st.session_state.agent_graph = None
    st.session_state.vault = CredentialVault()


def connect_database(db_uri: str):
    disconnect_db()
    st.session_state.vault = CredentialVault()
    with st.spinner("Connecting to database..."):
        try:
            st.session_state.vault.store_secret("active_db_uri", db_uri)
            
            mgr = DatabaseConnectionManager.from_uri(db_uri)
            mgr.verify_connection()
            st.session_state.conn_mgr = mgr

            engine = mgr.get_engine()
            catalog = CatalogInspector.inspect_engine(engine)
            st.session_state.catalog = catalog

            v_index = SchemaVectorIndex(catalog)
            st.session_state.vector_index = v_index

            llm = init_chat_model(DEFAULT_MODEL)
            executor = SandboxedExecutor(engine=engine, timeout_seconds=10)
            graph = create_sql_agent_graph(
                llm=llm,
                catalog=catalog,
                executor=executor,
                dialect=mgr.dialect_name,
                vector_index=v_index,
            )
            st.session_state.agent_graph = graph
            st.success(f"Connected to {mgr.dialect_name.upper()} ({len(catalog.tables)} tables)")
        except Exception as e:
            st.error(f"Connection failed: {e}")
            disconnect_db()


with st.sidebar:
    st.title("Talk2DB")
    st.caption("Natural language SQL interface")
    st.divider()

    st.subheader("Database Connection")
    conn_type = st.selectbox(
        "Connection Type",
        ["Default SQLite (company_sales.db)", "Database URI", "Credentials"],
    )

    if conn_type == "Default SQLite (company_sales.db)":
        target_uri = DEFAULT_DB_URI
        st.text_input("URI", value=target_uri, disabled=True)
    elif conn_type == "Database URI":
        target_uri = st.text_input(
            "URI",
            placeholder="postgresql://user:pass@localhost:5432/dbname",
        )
    else:
        dialect = st.selectbox("Dialect", ["mysql", "postgresql", "sqlite", "snowflake"])
        default_port = 3306 if dialect == "mysql" else 5432
        host = st.text_input("Host", value="localhost")
        port = st.number_input("Port", value=default_port, step=1)
        dbname = st.text_input("Database", value="ecommerce_db" if dialect == "mysql" else "mydb")
        user = st.text_input("Username", value="root" if dialect == "mysql" else "postgres")
        pwd = st.text_input("Password", type="password", value="")
        driver = st.text_input("Driver (Optional)", placeholder="pymysql, pg8000")

        from sqlalchemy.engine import URL
        selected_driver = driver.strip() if driver.strip() else ("pymysql" if dialect == "mysql" else ("pg8000" if dialect == "postgresql" else None))
        drivername = f"{dialect}+{selected_driver}" if selected_driver else dialect
        url_obj = URL.create(
            drivername=drivername,
            username=user.strip() or None,
            password=pwd or None,
            host=host.strip(),
            port=int(port),
            database=dbname.strip(),
        )
        target_uri = url_obj.render_as_string(hide_password=False)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Connect", use_container_width=True, type="primary"):
            connect_database(target_uri)
    with col2:
        if st.button("Disconnect", use_container_width=True):
            disconnect_db()
            st.info("Disconnected.")

    st.divider()

    if st.session_state.catalog is not None:
        st.subheader("Schema Explorer")
        cat = st.session_state.catalog
        st.caption(f"{len(cat.tables)} tables reflected")

        for tbl_name, tbl_meta in cat.tables.items():
            with st.expander(f"Table: {tbl_name}"):
                cols_data = [
                    {
                        "Column": c.name,
                        "Type": c.type,
                        "PK": "Yes" if c.primary_key else "",
                        "Nullable": "Yes" if c.nullable else "No",
                    }
                    for c in tbl_meta.columns
                ]
                st.dataframe(pd.DataFrame(cols_data), hide_index=True)
                if tbl_meta.foreign_keys:
                    st.markdown("**Foreign Keys:**")
                    for fk in tbl_meta.foreign_keys:
                        st.caption(f"- `{', '.join(fk.constrained_columns)}` -> `{fk.referred_table}`")


st.title("Talk2DB")
st.write("Ask natural language questions to query your database with automated SQL generation and analysis.")

if st.session_state.agent_graph is None:
    st.info("Connect to a database in the sidebar to get started.")
    st.stop()

user_query = st.chat_input("Ask a question about your data...")

quick_cols = st.columns(3)
with quick_cols[0]:
    if st.button("Total revenue by department / category"):
        user_query = "What is the total sales amount by department or category?"
with quick_cols[1]:
    if st.button("Top records by amount / salary"):
        user_query = "Show top records ordered by value descending."
with quick_cols[2]:
    if st.button("Recent transactions with details"):
        user_query = "Show recent sales or orders with joined entity names."

if user_query:
    st.markdown(f"**Question:** {user_query}")

    with st.spinner("Analyzing request and running query..."):
        result = st.session_state.agent_graph.invoke({
            "question": user_query,
            "max_attempts": 3,
        })

    telemetry = result.get("telemetry", {})
    attempts = result.get("attempts", 0) + 1
    duration = (
        telemetry.get("retrieval_duration_ms", 0)
        + telemetry.get("generation_duration_ms", 0)
        + telemetry.get("execution_duration_ms", 0)
        + telemetry.get("synthesis_duration_ms", 0)
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Dialect", result.get("dialect", "sqlite").upper())
    with m2:
        st.metric("Safety Guardrail", "Passed" if result.get("ast_valid") else "Failed")
    with m3:
        st.metric("Attempts", attempts)
    with m4:
        st.metric("Latency", f"{duration:.0f} ms")

    st.subheader("SQL Query")
    st.code(result.get("query", ""), language="sql")

    if result.get("error"):
        st.error(f"Execution Error: {result.get('error')}")

    df = result.get("dataframe")
    if df is not None and not df.empty:
        st.subheader("Results")
        st.dataframe(df, use_container_width=True)

        csv_bytes = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV",
            data=csv_bytes,
            file_name="results.csv",
            mime="text/csv",
        )
    elif df is not None and df.empty:
        st.warning("Query executed successfully, but returned 0 rows.")

    if result.get("final_answer"):
        st.subheader("Summary")
        st.info(result.get("final_answer"))
