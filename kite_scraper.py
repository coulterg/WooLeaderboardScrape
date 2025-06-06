import os
import time
import calendar
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import pandas as pd


def URLfromYearMonth(year, month, gender="male"):
    start = calendar.timegm(datetime(year, month, 1).timetuple())
    if month == 12:
        end = calendar.timegm(datetime(year + 1, 1, 1).timetuple()) - 1
    else:
        end = calendar.timegm(datetime(year, month + 1, 1).timetuple()) - 1
    return (
        f"https://leaderboards.woosports.com/?feature=height&game_type=big_air"
        f"&start_date={start}&end_date={end}&date_name=custom&gender={gender}"
    )


def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver_path = os.path.join("chromedriver-mac-x64", "chromedriver")
    service = Service(driver_path)  # this is the correct way to pass path now
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def scrape_table(driver, url):
    driver.get(url)
    time.sleep(3.5)
    try:
        text = driver.find_element("class name", "leaderboard-table").text
        return text
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def parse_table(text, month, year):
    rows = text.strip().split("\n")
    data = []
    for i in range(0, len(rows), 3):
        try:
            date = f"1/{month}/{year}"
            date_us = f"{month}/1/{year}"
            rank = rows[i]
            name = rows[i + 1]
            height = float(rows[i + 2][:-2])
            data.append([date, date_us, rank, name, height])
        except (IndexError, ValueError):
            continue
    return pd.DataFrame(data, columns=["Date", "Date_US", "Monthly_Rank", "Name", "Height_m"])


def extract_record_breakers(df):
    df = df.copy()
    df["new_record"] = 0

    for gender, group in df.groupby("Gender", sort=False):
        record = -1
        for date, frame in group.groupby("Date", sort=False):
            max_height = frame["Height_m"].max()
            if max_height > record:
                first_index = frame.index[frame["Height_m"] == max_height][0]
                df.loc[first_index, "new_record"] = 1
                record = max_height

    return df


def find_latest_date(df, gender):
    gender_df = df[df["Gender"] == gender].copy()
    if gender_df.empty:
        return 2013, 12

    gender_df["Year"] = pd.to_datetime(gender_df["Date"], format="%d/%m/%y").dt.year
    gender_df["Month"] = pd.to_datetime(gender_df["Date"], format="%d/%m/%y").dt.month

    latest = gender_df.sort_values(by=["Year", "Month"], ascending=False).iloc[0]
    year, month = int(latest["Year"]), int(latest["Month"])
    if month == 12:
        return year + 1, 1
    else:
        return year, month + 1


def main():
    os.makedirs("data", exist_ok=True)
    try:
        existing_df = pd.read_csv("data/all_records.csv")
    except FileNotFoundError:
        existing_df = pd.DataFrame(columns=["Name", "Height_m", "Year", "Month", "Gender"])

    all_data = []
    driver = setup_driver()
    now = datetime.now()

    for gender in ["male", "female"]:
        start_year, start_month = find_latest_date(existing_df, gender)

        for year in range(start_year, now.year + 1):
            for month in range(1, 13):
                if year == start_year and month < start_month:
                    continue
                if year == now.year and month >= now.month:
                    break

                url = URLfromYearMonth(year, month, gender)
                print(f"Scraping {year}-{month:02d} ({gender})...")
                text = scrape_table(driver, url)
                if text:
                    df = parse_table(text, month, year)
                    df["Year"] = year
                    df["Month"] = month
                    df["Gender"] = gender

                    df["Date"] = pd.to_datetime(dict(year=df["Year"], month=df["Month"], day=1)).dt.strftime("%d/%m/%y")
                    df["Date_US"] = pd.to_datetime(dict(year=df["Year"], month=df["Month"], day=1)).dt.strftime("%-m/%-d/%y")

                    df["Monthly_Rank"] = df["Height_m"].rank(ascending=False, method="first").astype(int)

                    all_data.append(df)

    driver.quit()

    new_df = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df = extract_record_breakers(combined_df)

    final_df = combined_df[["Date", "Date_US", "Monthly_Rank", "Name", "Height_m", "Gender", "new_record"]]
    final_df.to_csv("data/all_records.csv", index=False)
    final_df.to_csv("public_data/all_records.csv", index=False)


    print("Scraping complete.\n")
    print("Saved:")
    print("- All records to: data/all_records.csv")


if __name__ == "__main__":
    main()
