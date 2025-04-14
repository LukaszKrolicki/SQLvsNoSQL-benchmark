import os
import time
import csv
import mysql.connector
import pandas as pd
from faker import Faker
import random

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3309,
    "user": "user",
    "password": "password",
    "database": "testdb"
}

RECORD_COUNTS = [100, 1000, 10000, 100000]  

SELECT_QUERIES = {
    # -- Pobiera wszystkie kolumny z tabeli 'companies'
    # -- Filtruje firmy, których nazwa zawiera literę 'a' i stan (state) nie jest pusty
    # -- Wyniki są posortowane według nazwy firmy
    "level_1": """
        SELECT * FROM companies
        WHERE name LIKE '%a%' AND state IS NOT NULL
        ORDER BY name 
    """,

    # -- Pobiera tytuł pracy, lokalizację i typ zatrudnienia z tabeli 'postings'
    # -- Filtruje ogłoszenia, których nazwa firmy zawiera literę 'a'
    # -- Oraz ogłoszenia, które mają więcej niż 5 wyświetleń, aplikacje większe lub równe 0 oraz nie pozwalają na pracę zdalną
    # -- Wyniki są posortowane według lokalizacji, a potem tytułu pracy
    "level_2": """
            SELECT title, location, formatted_work_type
            FROM postings
            WHERE company_name LIKE '%a%'
            AND views > 5 AND applies >= 0 AND remote_allowed = 0
            ORDER BY location, title 
        """,

    # -- Pobiera nazwę firmy, tytuł pracy, lokalizację, typ pracy (np. pełny etat), oraz liczbę umiejętności związanych z danym ogłoszeniem
    # -- Łączy tabele 'companies', 'postings' i 'job_skills' aby uzyskać pełne informacje o pracy oraz umiejętnościach wymaganych w ogłoszeniu
    # -- Filtruje ogłoszenia, które mają lokalizację zawierającą literę 'a', typ pracy 'Full-time' oraz więcej niż 1 wyświetlenie
    # -- Liczy tylko ogłoszenia z co najmniej jednym wymaganym skill'em
    # -- Wyniki są posortowane według liczby umiejętności w ogłoszeniu(malejąco)
    "level_3": """
        SELECT c.name AS company_name, p.title AS job_title, p.location, p.formatted_work_type, COUNT(js.skill_abr) AS skill_count
        FROM companies c
        JOIN postings p ON c.company_id = p.company_id
        LEFT JOIN job_skills js ON p.job_id = js.job_id
        WHERE p.location LIKE '%a%' AND p.formatted_work_type = 'Full-time' AND p.views > 1
        GROUP BY c.name, p.title, p.location, p.formatted_work_type
        HAVING COUNT(js.skill_abr) > 0
        ORDER BY skill_count DESC 
    """,

    # -- Pobiera nazwę firmy, liczbę ogłoszeń o pracę, średnią liczbę wyświetleń ogłoszeń oraz liczbę unikalnych umiejętności wymaganych w ogłoszeniach
    # -- Łączy tabele 'companies', 'postings' i 'job_skills', aby uzyskać dane o ogłoszeniach i wymaganych umiejętnościach
    # -- Filtruje tylko ogłoszenia typu 'Full-time' oraz firmy, które mają przypisane ogłoszenia
    # -- Grupuje wyniki po firmach i liczy ogłoszenia, średnią liczbę wyświetleń i liczbę umiejętności
    # -- Filtruje tylko firmy z więcej niż 2 ogłoszeniami i średnią liczbą wyświetleń większą niż 1
    # -- Wyniki są posortowane najpierw według liczby ogłoszeń (malejąco), a potem według średniej liczby wyświetleń (malejąco)
    "level_4": """
        SELECT c.name AS company_name, COUNT(p.job_id) AS job_postings_count, AVG(p.views) AS avg_views, COUNT(js.skill_abr) AS total_skills
        FROM companies c
        JOIN postings p ON c.company_id = p.company_id
        LEFT JOIN job_skills js ON p.job_id = js.job_id
        WHERE p.formatted_work_type = 'Full-time' AND p.company_name IS NOT NULL
        GROUP BY c.company_id
        HAVING job_postings_count > 2 AND avg_views > 1
        ORDER BY job_postings_count DESC, avg_views DESC
    """
}

UPDATE_QUERIES = {
    # -- Aktualizuje stan ('state') na 'Updated' dla firm, których nazwa zawiera literę 'a'
    # -- Wybierane są tylko te firmy, których 'company_id' znajduje się w podzapytaniu,
    "level_1": """
        UPDATE companies
        SET state = 'Updated'
        WHERE company_id IN (
            SELECT company_id FROM (
                SELECT company_id
                FROM companies
                WHERE name LIKE '%a%' LIMIT {limit}
            ) AS temp 
        )
    """,

    # -- Aktualizuje liczbę wyświetleń ('views') dla ogłoszeń, których 'company_name' zawiera literę 'a'
    # -- Zwiększa liczbę wyświetleń o 1, jeżeli liczba 'views' jest NULL, używa COALESCE, aby zamienić NULL na 0 przed dodaniem 1
    # -- Wybierane są tylko ogłoszenia, których 'job_id' znajduje się w podzapytaniu,
    "level_2": """
        UPDATE postings
        SET views = COALESCE(views, 0) + 1
        WHERE job_id IN (
            SELECT job_id FROM (
                SELECT job_id
                FROM postings
                WHERE company_name LIKE '%a%' AND applies >= 0 LIMIT {limit}
            ) AS temp 
        )
    """,

    # -- Aktualizuje liczbę aplikacji ('applies') dla ogłoszeń, które spełniają określone warunki
    # -- Zwiększa liczbę aplikacji o 1, jeżeli liczba 'applies' jest NULL, używa COALESCE, aby zamienić NULL na 0 przed dodaniem 1
    # -- Ogłoszenia są wybierane na podstawie poniższych warunków:
    # -- 1. Liczba wyświetleń (views) < 10
    # -- 2. Stan firmy (state) nie jest NULL
    # -- 3. Kraj firmy to 'US'
    # -- 4. Nazwa firmy zawiera literę 'a'
    # -- Wybierane są tylko ogłoszenia, których 'job_id' znajduje się w podzapytaniu,
    "level_3": """
        UPDATE postings
        SET applies = COALESCE(applies, 0) + 1
        WHERE job_id IN (
            SELECT job_id FROM (
                SELECT p.job_id
                FROM postings p
                JOIN companies c ON p.company_id = c.company_id
                WHERE p.views < 10 AND c.state IS NOT NULL AND c.country= 'US' AND c.name LIKE '%a%' LIMIT {limit}
            ) AS temp 
        )
    """,

}

DELETE_QUERIES = {
    # -- Usuwa firmy z tabeli 'companies', których 'company_id' znajduje się w podzapytaniu
    # -- Podzapytanie wybiera firmy, których nazwa zawiera literę 'a'
    "level_1": """
        DELETE FROM companies 
        WHERE company_id IN (
            SELECT company_id FROM (
                SELECT company_id
                FROM companies
                WHERE name LIKE '%a%' LIMIT {limit}
            ) AS temp 
        )
    """,

    #   -- Usuwa ogłoszenia o pracę z tabeli 'postings', których 'job_id' znajduje się w podzapytaniu
    #   -- Podzapytanie wybiera ogłoszenia, które mają mniej niż 300 wyświetleń i mniej niż 100 aplikacji
    "level_2": """
        DELETE FROM postings
        WHERE job_id IN (
            SELECT job_id FROM (
                SELECT job_id
                FROM postings
                WHERE views < 300 AND applies <= 100 LIMIT {limit}
            ) AS temp
        )
    """,

    # -- Usuwa ogłoszenia o pracę z tabeli 'postings', których 'job_id' znajduje się w podzapytaniu
    # -- Podzapytanie wybiera ogłoszenia spełniające następujące warunki:
    # -- 1. Liczba wyświetleń (views) < 10
    # -- 2. Stan firmy (state) nie jest NULL
    # -- 3. Kraj firmy to 'US'
    # - 4. Nazwa firmy zawiera literę 'a'
    "level_3": """
        DELETE FROM postings
        WHERE job_id IN (
            SELECT job_id FROM (
                SELECT p.job_id
                FROM postings p
                JOIN companies c ON p.company_id = c.company_id
                WHERE p.views < 10 AND c.state IS NOT NULL AND c.country= 'US' AND c.name LIKE '%a%' LIMIT {limit}
            ) AS temp
        )
    """
}

fake = Faker()

def generate_fake_companies(count):
    unique_ids = set()
    companies = []

    while len(companies) < count:
        company_id = random.randint(1e9, 1e10)
        if company_id not in unique_ids:
            unique_ids.add(company_id)
            companies.append((
                company_id,
                fake.company(),
                fake.catch_phrase(),
                random.choice(['1-10', '11-50', '51-200', '201-500']),
                fake.state(),
                fake.country(),
                fake.city(),
                fake.zipcode(),
                fake.address(),
                fake.url()
            ))

    return companies

def run_select_query(cursor, query, limit):
    full_query = f"{query} LIMIT {limit}"
    start = time.time()
    cursor.execute(full_query)     # Wykonanie zapytania SQL na bazie danych.
    columns = cursor.column_names
    results = cursor.fetchall() # zwraca wsgizystkie wiersze wyników zapytania
    duration = time.time() - start
    df = pd.DataFrame(results, columns=columns)
    rows_affected = len(results)
    return df, duration, rows_affected

def run_insert_test(cursor, conn, count):
    cursor.execute("SELECT COUNT(*) FROM companies")
    before_count = cursor.fetchone()[0]
    data = generate_fake_companies(count)
    query = """
        INSERT INTO companies (company_id, name, description, company_size, state, country, city, zip_code, address, url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        start = time.time()
        cursor.executemany(query, data) # wykonuje zapytanie 'query' dla każdego wiersza w danych 'data'
        duration = time.time() - start
        cursor.execute("SELECT COUNT(*) FROM companies")
        after_count = cursor.fetchone()[0]
        conn.rollback()  # Anulowanie (rollback) transakcji, zmiany nie mają być zapisane do bazy

        return before_count, after_count, len(data), duration

    except Exception as e:
        conn.rollback()
        raise e

def run_update_test(cursor, conn, query):
    try:
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        start = time.time()
        cursor.execute(query)
        affected = cursor.rowcount # rowcount zwraca liczbę wierszy, które zostały zmienione przez zapytanie SQL
        duration = time.time() - start
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        return affected, duration
    except Exception as e:
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        raise e

def run_delete_test(cursor, conn, query):
    try:
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        start = time.time()
        cursor.execute(query)
        affected = cursor.rowcount
        duration = time.time() - start
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        return affected, duration
    except Exception as e:
        conn.rollback()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        raise e

def save_csv_result(mode, level, count, rows, duration):
    os.makedirs("time_results", exist_ok=True)
    summary_path = "time_results/benchmark_summary.csv"
    file_exists = os.path.isfile(summary_path)

    with open(summary_path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["mode", "query_level", "record_limit", "rows_affected", "execution_time_seconds"])
        writer.writerow([mode, level, count, rows, round(duration, 6)])
    print(f"Zapisano wynik: {summary_path}")


def save_insert_check(before, after, level, count):
    os.makedirs("query_insert_result", exist_ok=True)
    filename = f"query_insert_result/insert_check_{level}_{count}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["before_insert", "after_insert", "inserted_rows"])
        writer.writerow([before, after, after - before])

    print(f"Zapisano dane: {filename}")


def save_query_result(df, level, count):
    os.makedirs("query_results", exist_ok=True)
    filename = f"query_results/query_{level}_{count}.csv"
    df.to_csv(filename, index=False)
    print(f"Zapisano dane: {filename}")

def save_update_result(level, count, affected_rows):
    os.makedirs("query_update_result", exist_ok=True)
    filename = f"query_update_result/update_{level}_{count}.csv"
    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["level", "record_limit", "rows_updated"])
        writer.writerow([level, count, affected_rows])
    print(f"Zapisano dane: {filename}")

def main():
    conn = mysql.connector.connect(**MYSQL_CONFIG)
    cursor = conn.cursor() # 'cursor' jest obiektem wykorzystywanym do wykonywania zapytań SQL na bazie danych.


    print("Wybierz test do wykonania:")
    print("1. SELECT")
    print("2. INSERT")
    print("3. UPDATE")
    print("4. DELETE")
    choice = input("Wpisz 1, 2, 3 lub 4: ").strip()

    if choice not in ["1", "2", "3", "4"]:
        print("Nieprawidłowy wybór. Zakończono.")
        return

    mode = {
        "1": "select",
        "2": "insert",
        "3": "update",
        "4": "delete"
    }[choice]

    try:
        if mode == "select":
            for level, query in SELECT_QUERIES.items():
                for count in RECORD_COUNTS:
                    try:
                        df, duration, affected = run_select_query(cursor, query, count)
                        print(f"{level} | SELECT | {count} rows | Time: {duration:.4f}s | Rows fetched: {affected}")
                        save_query_result(df, level, count)
                        save_csv_result("select", level, count, affected, duration)
                    except Exception as e:
                        print(f"Błąd w SELECT {level} z {count} rekordami: {e}")

        elif mode == "insert":
            for count in RECORD_COUNTS:
                try:
                    before, after, rows, duration = run_insert_test(cursor, conn, count)
                    print(f"INSERT | {count} rows | Time: {duration:.4f}s | Before: {before} | After: {after}")
                    save_insert_check(before, after, "insert", count)
                    save_csv_result("insert", "insert", count, rows, duration)
                except Exception as e:
                    print(f"Błąd w INSERT z {count} rekordami: {e}")

        elif mode == "update":
            for level, query_template in UPDATE_QUERIES.items():
                for count in RECORD_COUNTS:
                    try:
                        query = query_template.format(
                            limit=count) if "{limit}" in query_template else query_template + f" LIMIT {count}"
                        affected, duration = run_update_test(cursor, conn, query)
                        print(f"{level} | UPDATE | {count} rows | Affected: {affected} | Time: {duration:.4f}s")
                        save_update_result(level, count, affected)
                        save_csv_result("update", level, count, affected, duration)

                    except Exception as e:

                        print(f"Błąd w UPDATE {level} z {count} rekordami: {e}")
        elif mode == "delete":
            for level, query_template in DELETE_QUERIES.items():
                for count in RECORD_COUNTS:
                    try:
                        query = query_template.format(
                            limit=count) if "{limit}" in query_template else query_template + f" LIMIT {count}"
                        affected, duration = run_delete_test(cursor, conn, query)
                        print(f"{level} | DELETE | {count} rows | Affected: {affected} | Time: {duration:.4f}s")
                        save_update_result(level, count, affected)  # Reuse update CSV format
                        save_csv_result("delete", level, count, affected, duration)
                    except Exception as e:
                        print(f"Błąd w DELETE {level} z {count} rekordami: {e}")

    except Exception as e:
        print(f"Nieoczekiwany błąd: {e}")

    finally:
        cursor.close()
        conn.close()
        print("Zakończono benchmark.")


if __name__ == "__main__":
    main()
