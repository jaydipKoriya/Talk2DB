import sqlite3

conn=sqlite3.connect('company_sales.db')
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    salary REAL
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER,
    amount REAL,
    sale_date DATE,
    FOREIGN KEY(employee_id) REFERENCES employees(id)
);

INSERT OR IGNORE INTO employees VALUES 
    (1, 'Alice Smith', 'Engineering', 95000),
    (2, 'Bob Johnson', 'Sales', 62000),
    (3, 'Charlie Lee', 'Sales', 71000);

INSERT OR IGNORE INTO sales VALUES 
    (1, 2, 12000.50, '2024-01-15'),
    (2, 2, 8500.00, '2024-02-20'),
    (3, 3, 15300.75, '2024-01-18');
""")
conn.commit()
conn.close()