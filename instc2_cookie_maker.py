from playwright.sync_api import sync_playwright
import json

def instagram_login_and_save_cookie(username, password, cookies_file="cookies.json"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headless=False so you can see login
        context = browser.new_context()
        page = context.new_page()

        print(" Logging in...")
        page.goto("https://www.instagram.com/accounts/login/")
        page.wait_for_timeout(3000)

        # Fill login form
        page.fill("input[name='username']", username)
        page.wait_for_timeout(1000)
        page.fill("input[name='password']", password)
        page.wait_for_timeout(1000)
        page.click("button[type='submit']")

        # Wait for login
        try:
            page.wait_for_url("https://www.instagram.com/", timeout=30000)
            print(" Logged in successfully")
        except:
            print(" Login may require manual intervention (2FA, captcha, etc.)")
            print(" Please complete login manually in the opened browser...")
            input("Press Enter once you're logged in and on the homepage...")

        # Save cookies after successful login
        cookies = context.cookies()
        with open(cookies_file, "w") as f:
            json.dump(cookies, f)
        print(f"Cookies saved to {cookies_file}")

        browser.close()

if __name__ == '__main__':
    USERNAME = "your_USERNAME_here"
    PASSWORD = "your_PASSWORD_here"
    instagram_login_and_save_cookie(USERNAME, PASSWORD)
