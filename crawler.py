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

# 初始化进度记录
def initialize_progress():
    if not os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'w') as f:
            json.dump({"current_url_index": 0, "page_num": 1, "jar_index": 0}, f)

# 读取进度
def load_progress():
    with open(PROGRESS_FILE, 'r') as f:
        return json.load(f)

# 保存进度
def save_progress(progress):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f)


# 从目标页面提取 client 链接
def fetch_client_links(url):
    response = requests.get(url)
    if response.status_code != 200:
        print(f"无法访问页面: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table')
    if not table:
        print("未找到表格。")
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
        return parts[2]  # group_id 在路径的第3部分
    return "unknown"

def download_jars(base_url):
    # 加载进度记录
    progress = load_progress()
    current_url_index = progress.get("current_url_index", 0)

    # 从中断的链接开始处理
    for url_index in range(current_url_index, len(client_links)):
        base_url = client_links[url_index]
        print(f"\n开始处理链接：{base_url}")
        # 提取 group_id 并动态调整下载路径
        group_id = get_group_id_from_url(base_url)
        download_path = os.path.join(os.path.expanduser("~"), "Desktop", "199", "jar", group_id)  # 设置下载路径
        os.makedirs(download_path, exist_ok=True)  # 如果不存在该文件夹则创建

        # 重置 page_num 和 jar_index 为新链接的初始值
        page_num = progress.get("page_num", 1)
        jar_index = progress.get("jar_index", 0)


        # 配置 Chrome 浏览器的下载路径，并禁用下载拦截
        chrome_options = webdriver.ChromeOptions()
        prefs = {
            "download.default_directory": download_path,
            "safebrowsing.enabled": True, # 禁用下载保护
            "profile.default_content_setting_values.automatic_downloads": 1 # 允许自动下载
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--headless")  # 无头模式
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.121 Safari/537.36") # 核心，模拟真实浏览器用户，添加此行代码后无头模式可以成功运行
        # 下面的代码删掉也可以正常运行
        chrome_options.add_argument("--window-size=1920,1080") # 浏览器窗口大小设置（没什么用）
        chrome_options.add_argument("--disable-blink-features=AutomationControlled") # 禁用 Blink 自动化检测 (disable-blink-features=AutomationControlled) 和其他禁用自动化的参数：这些参数虽然有助于某些严格检测的页面，但不一定是所有页面都需要。许多网站仅凭 User-Agent 识别，而这些额外的参数可能并不会直接影响内容加载。
        chrome_options.add_argument("--disable-gpu") #禁用GPU - 提高效率
        chrome_options.add_argument("--disable-extensions") #禁用扩展 - 提高效率
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"]) #这个参数会去掉 Chrome 浏览器的 "Chrome is being controlled by automated test software" 信息提示。它主要用于消除浏览器在被 Selenium 控制时暴露的自动化特征，从而减少被检测为机器人的风险。
        chrome_options.add_experimental_option("useAutomationExtension", False)  #禁用 Chrome 的自动化扩展（即 Selenium 的自动化扩展），避免因自动化扩展被检测到而影响页面加载。

        # 用于存储所有 clients 的链接
        all_clients = []

        # 步骤 1：遍历每一页获取 client 链接，直到没有新内容
        while True:

            # 使用当前页码构建页面 URL / 从记录处继续下载
            current_url = f"{base_url}{page_num}"

            # 初始化浏览器并加载当前页面
            driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"  # 替换为对应Chrome浏览器版本的 ChromeDriver 版本的实际路径
            driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
            driver.get(current_url)

            try:
                # 等待页面加载完成
                WebDriverWait(driver, 20).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".im .im-title a:not([href*='usages'])"))
                )
                print(f"页面 {page_num} 加载成功，开始提取 client 链接。")

                # 提取 client 链接
                clients = driver.find_elements(By.CSS_SELECTOR, ".im .im-title a:not([href*='usages'])")
                if not clients:
                    print("没有更多 client 链接，已到达最后一页。")
                    break

                for client in clients:
                    client_name = client.text
                    client_link = client.get_attribute('href')
                    all_clients.append((client_name, client_link))
                    print(f"Client Name: {client_name}, Client Link: {client_link}")

            except Exception as e:
                print(f"页面加载失败或出错，可能已到达最后一页。错误信息：{e}")
                break

            finally:
                # 关闭当前浏览器窗口
                driver.quit()

            # 步骤 2：获取最新版本链接
            # 从上次中断的 JAR 包索引开始
            for idx in range(jar_index, len(all_clients)):
                client_name, client_link = all_clients[idx]

                driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"  # 替换为对应Chrome浏览器版本的 ChromeDriver 版本的实际路径
                driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
                driver.get(client_link)

                try:
                    WebDriverWait(driver, 20).until(
                         EC.presence_of_element_located((By.CSS_SELECTOR, ".grid .vbtn.release"))
                    )
                    latest_version_button = driver.find_element(By.CSS_SELECTOR, ".grid .vbtn")
                    latest_version_link = latest_version_button.get_attribute("href")
                    print(f"{client_name} 的最新版本链接：{latest_version_link}")

                except Exception as e:
                    print(f"{client_name} 页面加载版本失败。错误信息：{e}")

                finally:
                    # 关闭当前浏览器窗口
                    driver.quit()

                # 步骤 3 ：获取并下载 jar 文件链接
                driver_path = r"D:\ChromeDriver\chromedriver-win64\chromedriver.exe"  # 替换为对应Chrome浏览器版本的 ChromeDriver 版本的实际路径
                driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
                driver.get(latest_version_link)

                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='.jar']"))
                    )
                    jar_button = driver.find_element(By.CSS_SELECTOR, "a[href*='.jar']")
                    jar_link = jar_button.get_attribute("href")

                    # 直接访问 jar 文件链接，开始下载
                    driver.get(jar_link)
                    print(f"{client_name} 的 jar 文件正在下载：{jar_link}")

                    # 等待一段时间确保文件下载完成（根据需要调整时间）
                    time.sleep(5)

                except Exception as e:
                    print(f"{client_name} 的 jar 文件链接未找到或下载失败。错误信息：{e}")

                finally:
                    # 关闭当前浏览器窗口
                    driver.quit()

                # 更新进度
                jar_index = idx + 1
                progress["jar_index"] = jar_index
                save_progress(progress)

            # 页面处理完毕，重置 jar_index，加载下一页
            jar_index = 0
            page_num += 1
            progress["page_num"] = page_num
            progress["jar_index"] = jar_index
            save_progress(progress)

        # 当前链接处理完毕，更新 URL 索引并重置 page_num 和 jar_index
        progress["current_url_index"] = url_index + 1
        progress["page_num"] = 1
        progress["jar_index"] = 0
        save_progress(progress)

    print("\n所有 jar 文件下载完成。文件已保存到指定目录。")


# 主程序
if __name__ == "__main__":
    # 加载进度
    initialize_progress()
    # 获取 client 链接
    client_page_url = "https://github.com/sormuras/modules/blob/main/doc/Top1000-2023.txt.md"
    client_links = fetch_client_links(client_page_url)

    # 循环传入每个 artifact 链接到下载函数
    if client_links:
        for base_url in client_links:
            download_jars(base_url)
    else:
        print("未能获取任何 client 链接。")