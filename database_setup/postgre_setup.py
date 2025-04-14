import psycopg2
import pandas as pd
import os
from datetime import datetime

# PostgreSQL configuration
POSTGRES_CONFIG = {
    "host": "localhost",
    "port": 5435,
    "user": "user",
    "password": "password",
    "database": "testdb"
}

# CSV file paths
CSV_DIR = "../data"
FILES = {
    "companies": "companies/companies.csv",
    "company_industries": "companies/company_industries.csv",
    "company_specialities": "companies/company_specialities.csv",
    "employee_counts": "companies/employee_counts.csv",
    "benefits": "jobs/benefits.csv",
    "job_industries": "jobs/job_industries.csv",
    "job_skills": "jobs/job_skills.csv",
    "salaries": "jobs/salaries.csv",
    "industries": "mappings/industries.csv",
    "skills": "mappings/skills.csv",
    "postings": "postings.csv"
}

# Define table schemas
TABLE_SCHEMAS = {
    "companies": """
        CREATE TABLE companies (
            company_id BIGINT PRIMARY KEY,
            name VARCHAR(255),
            description VARCHAR(255),
            company_size VARCHAR(255),
            state VARCHAR(255),
            country VARCHAR(255),
            city VARCHAR(255),
            zip_code VARCHAR(255),
            address VARCHAR(255),
            url VARCHAR(255)
        )
    """,
    "company_industries": """
        CREATE TABLE company_industries (
            company_id BIGINT,
            industry VARCHAR(255),
            PRIMARY KEY (company_id, industry),
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """,
    "company_specialities": """
        CREATE TABLE company_specialities (
            company_id BIGINT,
            speciality VARCHAR(255),
            PRIMARY KEY (company_id, speciality),
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """,
    "employee_counts": """
        CREATE TABLE employee_counts (
            company_id BIGINT,
            employee_count INT,
            follower_count INT,
            time_recorded TIMESTAMP,
            PRIMARY KEY (company_id, time_recorded),
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """,
    "industries": """
        CREATE TABLE industries (
            industry_id BIGINT PRIMARY KEY,
            industry_name VARCHAR(255)
        )
    """,
    "skills": """
        CREATE TABLE skills (
            skill_abr VARCHAR(255) PRIMARY KEY,
            skill_name VARCHAR(255)
        )
    """,
    "postings": """
        CREATE TABLE postings (
            job_id BIGINT PRIMARY KEY,
            company_id BIGINT,
            company_name VARCHAR(255),
            title VARCHAR(255),
            description VARCHAR(255),
            max_salary FLOAT,
            pay_period VARCHAR(255),
            location VARCHAR(255),
            views INT,
            med_salary FLOAT,
            min_salary FLOAT,
            formatted_work_type VARCHAR(255),
            applies INT,
            original_listed_time TIMESTAMP,
            remote_allowed INT,
            job_posting_url VARCHAR(255),
            application_url VARCHAR(255),
            application_type VARCHAR(255),
            expiry TIMESTAMP,
            closed_time TIMESTAMP,
            formatted_experience_level VARCHAR(255),
            skills_desc VARCHAR(255),
            listed_time TIMESTAMP,
            posting_domain VARCHAR(255),
            sponsored INT,
            work_type VARCHAR(255),
            currency VARCHAR(255),
            compensation_type VARCHAR(255),
            normalized_salary FLOAT,
            zip_code VARCHAR(255),
            fips VARCHAR(255),
            FOREIGN KEY (company_id) REFERENCES companies(company_id)
        )
    """,
    "job_industries": """
        CREATE TABLE job_industries (
            job_id BIGINT,
            industry_id BIGINT,
            PRIMARY KEY (job_id, industry_id),
            FOREIGN KEY (job_id) REFERENCES postings(job_id),
            FOREIGN KEY (industry_id) REFERENCES industries(industry_id)
        )
    """,
    "job_skills": """
        CREATE TABLE job_skills (
            job_id BIGINT,
            skill_abr VARCHAR(255),
            PRIMARY KEY (job_id, skill_abr),
            FOREIGN KEY (job_id) REFERENCES postings(job_id),
            FOREIGN KEY (skill_abr) REFERENCES skills(skill_abr)
        )
    """,
    "benefits": """
        CREATE TABLE benefits (
            job_id BIGINT,
            inferred INT,
            type VARCHAR(255),
            PRIMARY KEY (job_id, type),
            FOREIGN KEY (job_id) REFERENCES postings(job_id)
        )
    """,
    "salaries": """
        CREATE TABLE salaries (
            salary_id BIGINT PRIMARY KEY,
            job_id BIGINT,
            max_salary FLOAT,
            med_salary FLOAT,
            min_salary FLOAT,
            pay_period VARCHAR(255),
            currency VARCHAR(255),
            compensation_type VARCHAR(255),
            FOREIGN KEY (job_id) REFERENCES postings(job_id)
        )
    """
}

# Function to create table if not exists
def create_table_if_not_exists(table_name):
    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    # Disable foreign key checks
    cursor.execute("SET session_replication_role = 'replica'")

    # Create the table with the defined schema
    cursor.execute(TABLE_SCHEMAS[table_name])

    # Enable foreign key checks
    cursor.execute("SET session_replication_role = 'origin'")

    conn.commit()
    cursor.close()
    conn.close()

# Function to correct datetime values
def correct_datetime(value):
    try:
        # Convert the value to an integer timestamp
        timestamp = int(float(value) / 1000)
        # Convert the timestamp to a datetime object
        corrected_datetime = datetime.fromtimestamp(timestamp)
        return corrected_datetime.strftime('%Y-%m-%d')
    except (ValueError, OverflowError):
        # Return a default datetime value if conversion fails
        return '1970-01-01'

# Function to get company_id based on company_name
def get_company_id(company_name, cursor):
    cursor.execute("SELECT company_id FROM companies WHERE name = %s", (company_name,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return None

# Function to ensure job_id exists in postings table
def ensure_job_id_exists(job_id, cursor):
    cursor.execute("SELECT COUNT(*) FROM postings WHERE job_id = %s", (job_id,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO postings (job_id) VALUES (%s)", (job_id,))

# Function to import CSV to PostgreSQL
def import_csv_to_postgres(table_name, file_path):
    print(f"Importing data from {file_path} to {table_name}...")
    file_path = os.path.join(CSV_DIR, file_path)
    if not os.path.exists(file_path):
        print(f"File {file_path} does not exist!")
        return

    df = pd.read_csv(file_path, low_memory=False)
    print(f"Importing {table_name}...")

    create_table_if_not_exists(table_name)

    # Correct datetime values in the 'time_recorded' column
    if 'time_recorded' in df.columns:
        df['time_recorded'] = df['time_recorded'].apply(correct_datetime)

    # Correct datetime values in other datetime columns
    datetime_columns = ['original_listed_time', 'expiry', 'closed_time', 'listed_time']
    for col in datetime_columns:
        if col in df.columns:
            df[col] = df[col].apply(correct_datetime)

    conn = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = conn.cursor()

    columns = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    update_columns = ", ".join([f"{col}=EXCLUDED.{col}" for col in df.columns])
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    for _, row in df.iterrows():
        try:
            # Replace NaN values with None
            row = row.where(pd.notnull(row), None)
            # Truncate columns if they exceed the maximum length
            row = {col: (val[:255] if isinstance(val, str) and len(val) > 255 else val) for col, val in row.items()}
            # Ensure job_id exists in postings table before inserting into job_industries table
            if table_name == 'job_industries':
                ensure_job_id_exists(row['job_id'], cursor)
            cursor.execute(sql, tuple(row.values()))
            conn.commit()  # Commit after each successful insert
        except psycopg2.DataError as e:
            print(f"Data error for row {row.get('job_id', 'N/A')}: {e}")
        except psycopg2.IntegrityError as e:
            print(f"Integrity error for row {row.get('job_id', 'N/A')}: {e}")
            conn.rollback()
            continue

    cursor.close()
    conn.close()
    print(f"Imported {len(df)} records into {table_name}!")

# Connect to PostgreSQL and import data
def main():
    print("Test:")
    try:
        print("Connecting:")
        conn = psycopg2.connect(**POSTGRES_CONFIG, connect_timeout=30)
        print("Connected to PostgreSQL successfully!")
        conn.close()
    except Exception as e:
        print(f"Connection error: {e}")
        return

    # Ensure the tables are created in the specified order
    table_order = [
        'companies',
        'postings',
        'company_industries', 'company_specialities', 'employee_counts', 'industries', 'skills',
        'job_industries', 'benefits', 'salaries',
        'job_skills'
    ]

    for table in table_order:
        import_csv_to_postgres(table, FILES[table])

if __name__ == "__main__":
    main()