import json
import os
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

PROGRESS_FILE = "progress.json"

# Initialize progress record
def initialize_progress():
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({"current_url_index": 0, "page_num": 1, "jar_index": 0}, f)

# Load progress
def load_progress():
    with open(PROGRESS_FILE, 'r') as f:
        return json.load(f)

# Save progress
def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


# Extract client links from the target page
def fetch_client_links(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Unable to access the page: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not table:
        print("Table not found.")
        return []

    rows = table.find_all('tr')
    client_links = []
    for row in rows:
        cells = row.find_all('td')
        if len(cells) >= 3 and '🧩' in cells[0].text:
            artifact = cells[2].text.strip()
            if ":" in artifact:
                group_id, artifact_id = artifact.split(":")
                link = f"https://mvnrepository.com/artifact/{group_id}/{artifact_id}/usages?p="
                client_links.append(link)
    return client_links

def get_group_id_from_url(url):
    parsed_url = urlparse(url)
    parts = parsed_url.path.split('/')
    if len(parts) > 3:
        return parts[2]  # group_id is in the 3rd part of the path
    return "unknown"

def download_jars(base_url):
    # Load progress record
    progress = load_progress()
    current_url_index = progress.get("current_url_index", 0)

    # Start processing from the interrupted link
    for url_index in range(current_url_index, len(client_links)):
        base_url = client_links[url_index]
        print(f"\nStarting to process the link: {base_url}")
        # Extract group_id and dynamically adjust the download path
        group_id = get_group_id_from_url(base_url)
        download_path = os.path.join(os.path.expanduser("~"), "Desktop", "199", "jar", group_id)  # Set the download path
        os.makedirs(download_path, exist_ok=True)  # Create the folder if it doesn't exist

        # Reset page_num and jar_index to the initial values for the new link
        page_num = progress.get("page_num", 1)
        jar_index = progress.get("jar_index", 0)

        # Configure Chrome browser download settings and disable download interception
        chrome_options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": download_path,
            "safebrowsing.enabled": True,  # Disable download protection
            "profile.default_content_setting_values.automatic_downloads": 1  # Allow automatic downloads
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")  # Headless mode
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36")  # Simulate a real browser user
        chrome_options.add_argument("--window-size=1920,1080")  # Set browser window size
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Disable Blink automation detection
        chrome_options.add_argument("--disable-gpu")  # Disable GPU - improve efficiency
        chrome_options.add_argument("--disable-extensions")  # Disable extensions - improve efficiency
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])  # Remove "Chrome is being controlled by automated test software" message
        chrome_options.add_experimental_option("useAutomationExtension", False)  # Disable Chrome automation extension

        # Store all client links
        all_clients = []

        # Step 1: Traverse each page to get client links until no new content
        while True:
            # Construct page URL using the current page number
            current_url = f"{base_url}{page_num}"

            # Initialize the browser and load the current page
            driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"  # Replace with the actual path of the ChromeDriver version matching your Chrome browser
            driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
            driver.get(current_url)

            try:
                # Wait for the page to load completely
                WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".im .im-title a:not([href*='usages'])"))
                )
                print(f"Page {page_num} loaded successfully, extracting client links.")

                # Extract client links
                clients = driver.find_elements(By.CSS_SELECTOR, ".im .im-title a:not([href*='usages'])")
                if not clients:
                    print("No more client links, reached the last page.")
                    break

                for client in clients:
                    client_name = client.text
                    client_link = client.get_attribute('href')
                    all_clients.append((client_name, client_link))
                    print(f"Client Name: {client_name}, Client Link: {client_link}")

            except Exception as e:
                print(f"Page load failed or error occurred, possibly reached the last page. Error message: {e}")
                break

            finally:
                # Close the current browser window
                driver.quit()

            # Step 2: Get the latest version links
            for idx in range(jar_index, len(all_clients)):
                client_name, client_link = all_clients[idx]

                driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"  # Replace with the actual path of the ChromeDriver version matching your Chrome browser
                driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
                driver.get(client_link)

                try:
                    WebDriverWait(driver, 20).until(
                         EC.presence_of_element_located((By.CSS_SELECTOR, ".grid .vbtn.release"))
                    )
                    latest_version_button = driver.find_element(By.CSS_SELECTOR, ".grid .vbtn")
                    latest_version_link = latest_version_button.get_attribute("href")
                    print(f"Latest version link for {client_name}: {latest_version_link}")

                except Exception as e:
                    print(f"Failed to load the version page for {client_name}. Error message: {e}")

                finally:
                    # Close the current browser window
                    driver.quit()

                # Step 3: Get and download the jar file link
                driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"  # Replace with the actual path of the ChromeDriver version matching your Chrome browser
                driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
                driver.get(latest_version_link)

                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.jar']"))
                    )
                    jar_button = driver.find_element(By.CSS_SELECTOR, "a[href*='.jar']")
                    jar_link = jar_button.get_attribute("href")

                    # Directly visit the jar file link to start the download
                    driver.get(jar_link)
                    print(f"Downloading the jar file for {client_name}: {jar_link}")

                    # Wait for some time to ensure the file download is complete (adjust time as needed)
                    time.sleep(5)

                except Exception as e:
                    print(f"Failed to find or download the jar file link for {client_name}. Error message: {e}")

                finally:
                    # Close the current browser window
                    driver.quit()

                # Update progress
                jar_index = idx + 1
                progress["jar_index"] = jar_index
                save_progress(progress)

            # Reset jar_index and load the next page
            jar_index = 0
            page_num += 1
            progress["page_num"] = page_num
            progress["jar_index"] = jar_index
            save_progress(progress)

        # Update the URL index and reset page_num and jar_index
        progress["current_url_index"] = url_index + 1
        progress["page_num"] = 1
        progress["jar_index"] = 0
        save_progress(progress)

    print("\nAll jar files have been downloaded. Files are saved in the specified directory.")


# Main program
if __name__ == "__main__":
    # Load progress
    initialize_progress()
    # Get client links
    client_page_url = "https://github.com/sormuras/modules/blob/main/doc/Top1000-2023.txt.md"
    client_links = fetch_client_links(client_page_url)

    # Pass each artifact link to the download function
    if client_links:
        for base_url in client_links:
            download_jars(base_url)
    else:
        print("Failed to retrieve any client links.")
