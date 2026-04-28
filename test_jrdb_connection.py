import pyodbc

JRDB_CONNECTION_STRING = (
    "Driver={ODBC Driver 17 for SQL Server};"
    "Server=13.89.241.33,1433;"
    "Database=JRDB;"
    "UID=jrdb;"
    "PWD=30j8Wp9E07e#;"
    "Encrypt=yes;"
    "TrustServerCertificate=yes;"
)

try:
    conn = pyodbc.connect(JRDB_CONNECTION_STRING)
    cursor = conn.cursor()

    cursor.execute("SELECT @@VERSION")
    row = cursor.fetchone()

    print("✅ Connection successful!")
    print("SQL Server version:")
    print(row[0])

    cursor.close()
    conn.close()

except Exception as e:
    print("❌ Connection failed")
    print(e)