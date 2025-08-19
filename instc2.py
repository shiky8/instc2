from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import asyncio
import time
import json
import os
from pathlib import Path
import re
import random
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont
import math
import subprocess
import traceback

class InstagramBot:
    def __init__(self, username: str, password: str, cookies_file: str = "cookies.json", headless: bool = True):
        self.username = username
        self.password = password
        self.cookies_file = cookies_file
        self.headless = headless
        self.context = None
        self.browser = None
        self.page = None
        self.playwright = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def _init_browser(self):
        """Initialize browser with optimized settings"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox', 
                '--disable-web-security',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--disable-extensions',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
        )
        
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale='en-US'
        )
        
        self.page = await self.context.new_page()
        self.page.set_default_timeout(30000)
        
    async def _random_delay(self, min_ms: int = 500, max_ms: int = 2000):
        """Random delay to mimic human behavior"""
        delay = random.randint(min_ms, max_ms)
        await self.page.wait_for_timeout(delay)
    
    async def _load_cookies(self) -> bool:
        """Load saved cookies if available"""
        try:
            if os.path.exists(self.cookies_file):
                with open(self.cookies_file, "r") as f:
                    cookies = json.load(f)
                await self.context.add_cookies(cookies)
                return True
        except Exception as e:
            print(f" Failed to load cookies: {e}")
        return False
    
    async def _save_cookies(self):
        """Save current cookies"""
        try:
            cookies = await self.context.cookies()
            with open(self.cookies_file, "w") as f:
                json.dump(cookies, f)
            print(" Cookies saved")
        except Exception as e:
            print(f" Failed to save cookies: {e}")
    
    async def _login(self) -> bool:
        """Login to Instagram with improved reliability"""
        print(" Logging in...")
        
        try:
            await self.page.goto("https://www.instagram.com/accounts/login/", wait_until='domcontentloaded')
            
            # Wait for login form
            await self.page.wait_for_selector("input[name='username']", timeout=15000)
            
            # Fill credentials with human-like typing
            username_input = self.page.locator("input[name='username']")
            password_input = self.page.locator("input[name='password']")
            
            await username_input.click()
            await self._random_delay(500, 1000)
            await username_input.type(self.username, delay=random.randint(50, 150))
            
            await self._random_delay(500, 1000)
            await password_input.click()
            await self._random_delay(500, 1000)
            await password_input.type(self.password, delay=random.randint(50, 150))
            
            await self._random_delay(1000, 2000)
            
            # Submit login
            login_button = self.page.locator("button[type='submit']")
            await login_button.click()
            
            # Wait for login result
            try:
                await self.page.wait_for_url("https://www.instagram.com/", timeout=20000)
                print("Logged in successfully")
                await self._save_cookies()
                return True
            except PlaywrightTimeoutError:
                # Check if there's an error or 2FA requirement
                if await self.page.locator("text=Sorry, your password was incorrect").is_visible():
                    print(" Invalid credentials")
                    return False
                elif await self.page.locator("text=We've sent you a security code").is_visible():
                    print("2FA required - please complete manually")
                    input("Complete 2FA and press Enter...")
                    await self._save_cookies()
                    return True
                else:
                    print("Login timeout - may need manual intervention")
                    return False
                    
        except Exception as e:
            print(f" Login failed: {e}")
            return False
    
    async def _check_login_status(self) -> bool:
        """Check if already logged in"""
        try:
            await self.page.goto("https://www.instagram.com/", wait_until='domcontentloaded', timeout=15000)
            await self._random_delay(2000, 3000)
            
            # Check for logged in indicators
            if (await self.page.locator("[aria-label='New post']").is_visible(timeout=5000) or
                await self.page.locator("[data-testid='new-post-button']").is_visible(timeout=2000) or
                await self.page.locator("svg[aria-label='New post']").is_visible(timeout=2000)):
                print("Already logged in")
                return True
                
        except Exception as e:
            print(f"Error checking login status: {e}")
        
        return False
    
    async def ensure_login(self) -> bool:
        """Ensure user is logged in"""
        if not self.browser:
            await self._init_browser()
        
        # Try loading cookies first
        if await self._load_cookies() and await self._check_login_status():
            return True
        
        # Login if cookies didn't work
        return await self._login()
    
    async def post_image(self, image_path: str, caption: str = "") -> bool:
        """Post an image with improved reliability"""
        
        # Validate image
        if not os.path.exists(image_path):
            print(f" Image file not found: {image_path}")
            return False
        
        valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        if Path(image_path).suffix.lower() not in valid_extensions:
            print(f" Invalid file format. Supported: {valid_extensions}")
            return False
        
        # Ensure logged in
        if not await self.ensure_login():
            print(" Failed to login")
            return False
        
        try:
            print(" Starting new post...")
            
            # Navigate to home if needed
            if not self.page.url.startswith("https://www.instagram.com"):
                await self.page.goto("https://www.instagram.com/", wait_until='domcontentloaded')
                await self._random_delay(2000, 3000)
            
            # Click create button with multiple fallback selectors
            create_selectors = [
                "[aria-label='New post']",
                "svg[aria-label='New post']",
                "[data-testid='new-post-button']",
                "a[href='/create/select/']",
                "div:has-text('Create')",
                "button:has-text('Create')"
            ]
            
            clicked = False
            for selector in create_selectors:
                try:
                    element = self.page.locator(selector).first
                    if await element.is_visible(timeout=3000):
                        await element.click()
                        clicked = True
                        print("Clicked create button")
                        break
                except:
                    continue
            
            if not clicked:
                print(" Could not find create button")
                return False
            
            await self._random_delay(2000, 3000)
            
            # Upload image
            print(f" Uploading: {image_path}")
            file_input = self.page.locator("input[type='file']").first
            await file_input.set_input_files(image_path)
            print("Image uploaded")
            
            await self._random_delay(3000, 4000)
            
            # Handle cropping options
            print("Handling crop options...")
            try:
                # First try to select "Original" size if available
                crop_selectors = [
                    "button svg[aria-label='Select crop']",
                    "[aria-label='Select crop']",
                    "button:has-text('Original')",
                    "span:has-text('Original')"
                ]
                
                for selector in crop_selectors:
                    try:
                        crop_btn = self.page.locator(selector).first
                        if await crop_btn.is_visible(timeout=3000):
                            await crop_btn.click()
                            print("Opened crop options")
                            await self._random_delay(1500, 2000)
                            
                            # Try to select original
                            original_selectors = [
                                'span:has-text("Original")',
                                "button:has-text('Original')",
                                "[aria-label='Original']",
                                "div:has-text('Original')"
                            ]
                            
                            for orig_sel in original_selectors:
                                try:
                                    orig_btn = self.page.locator(orig_sel).first
                                    if await orig_btn.is_visible(timeout=2000):
                                        await orig_btn.click()
                                        print("Selected original size")
                                        await self._random_delay(1000, 1500)
                                        break
                                except:
                                    continue
                            break
                    except:
                        continue
            except Exception as e:
                print(f"Could not handle crop options: {e}")
            
            # Skip cropping - click Next
            await self._click_next_button("Proceeding to next step...")
            await self._random_delay(2000, 3000)
            
            # Skip filters - click Next
            await self._click_next_button("Skipping filters...")
            await self._random_delay(2000, 3000)
            
            # Add caption if provided
            if caption:
                print(f" Adding caption: {caption[:50]}...")
                caption_selectors = [
                    "textarea[aria-label*='caption']",
                    "textarea[placeholder*='caption']",
                    "div[aria-label*='caption']",
                    "textarea"
                ]
                
                for selector in caption_selectors:
                    try:
                        caption_input = self.page.locator(selector).first
                        if await caption_input.is_visible(timeout=3000):
                            await caption_input.fill(caption)
                            print("Caption added")
                            break
                    except:
                        continue
            
            # Share the post
            print(" Publishing post...")
            share_selectors = [
                "div[role='button']:has-text('Share')",
                "button:has-text('Share')",
                "[aria-label='Share']"
            ]
            
            shared = False
            for selector in share_selectors:
                try:
                    share_button = self.page.locator(selector).first
                    if await share_button.is_visible(timeout=5000):
                        await share_button.click()
                        shared = True
                        print("Post shared!")
                        break
                except:
                    continue
            
            if not shared:
                print(" Could not find share button")
                self.post_image( image_path, caption)
                # return False
            
            # Wait for success
            print(" Waiting for post confirmation...")
            await self._random_delay(8000, 12000)
            
            # Check for success indicators
            if (await self.page.locator("text=Your post has been shared").is_visible(timeout=5000) or
                self.page.url.startswith("https://www.instagram.com/p/") or
                await self.page.locator("[aria-label='Activity Feed']").is_visible(timeout=3000)):
                print(" Post published successfully!")
                return True
            else:
                print("Post process completed")
                return True
                
        except Exception as e:
            print(f" Error posting image: {e}")
            return False
    
    async def _click_next_button(self, message: str):
        """Helper to click Next button with fallbacks"""
        print(message)
        next_selectors = [
            "div[role='button']:has-text('Next')",
            "button:has-text('Next')",
            "[aria-label='Next']",
            "div:has-text('Next')",
            "text=Next"
        ]
        
        for selector in next_selectors:
            try:
                next_button = self.page.locator(selector).first
                if await next_button.is_visible(timeout=3000):
                    await next_button.click()
                    return
            except:
                continue
    
    async def get_last_post_url(self, max_retries: int = 5) -> Optional[str]:
        """Get the URL of the most recent post with retries"""
        profile_url = f"https://www.instagram.com/{self.username}/"
        
        for attempt in range(max_retries):
            try:
                print(f" Getting last post URL (attempt {attempt + 1}/{max_retries})")
                
                if not await self.ensure_login():
                    continue
                
                await self.page.goto(profile_url, wait_until='domcontentloaded', timeout=30000)
                await self._random_delay(5000, 7000)
                
                # Multiple selectors for post links
                post_selectors = [
                    "article a",
                    "a[href*='/p/']",
                    "div._aagu a",
                    "a.x1i10hfl[href*='/p/']",
                    "a[role='link'][href*='/p/']",
                    "[class*='_aagu'] a",
                    "div[style*='padding-bottom'] a"
                ]
                
                # Try each selector
                for selector in post_selectors:
                    try:
                        print(f"  Trying selector: {selector}")
                        await self.page.wait_for_selector(selector, timeout=10000)
                        
                        post_links = await self.page.locator(selector).all()
                        print(f"  Found {len(post_links)} post links")
                        
                        if post_links:
                            # Get the first post link (most recent)
                            href = await post_links[0].get_attribute("href")
                            if href and "/p/" in href:
                                full_url = f"https://www.instagram.com{href}"
                                print(f"Found last post: {full_url}")
                                return full_url
                                
                    except Exception as e:
                        print(f"    Selector {selector} failed: {e}")
                        continue
                
                # If no selectors worked, try getting all links and filtering
                try:
                    print("  Trying fallback method - getting all links...")
                    all_links = await self.page.locator("a[href*='/p/']").all()
                    if all_links:
                        href = await all_links[0].get_attribute("href")
                        if href:
                            full_url = f"https://www.instagram.com{href}"
                            print(f"Found last post (fallback): {full_url}")
                            return full_url
                except:
                    pass
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await self._random_delay(5000, 8000)
        
        print(" Failed to get last post URL after all attempts")
        return None

def filter_real_comments(comments, username):
    """Filter out usernames, UI elements, timestamps, and other non-comment text"""
    
    # UI elements and navigation items to exclude
    ui_elements = {
        "reply","Start the conversation.","Now","SHIKY terminal", "my terminal_c1","like", "replies", "view replies", "hide replies", "view more replies",
        "home", "search", "explore", "reels", "messages", "notifications", "create", "profile", "more",
        "meta", "about", "blog", "jobs", "help", "api", "privacy", "terms", "locations",
        "instagram lite", "meta ai", "meta ai articles", "threads", "contact uploading", "non-users",
        "meta verified", "english", "© 2025 instagram from meta", "also from meta",
        "follow", "following", "followers", "posts", "tagged", "saved",
        "share", "copy link", "embed", "report", "block", "restrict",
        "view more comments", "contact uploading & non-users",
        "load more comments", "see more", "show more", "hide", "show less",
        "translate", "see translation", "see original", "verified", "sponsored",
        "add a comment", "post", "cancel", "done", "edit", "delete",
        "story", "stories", "highlights", "live", "igtv", "shop", "shopping"
    }
    
    filtered_comments = []
    
    for comment in comments:
        if not comment:
            continue
            
        comment = comment.strip()
        comment_lower = comment.lower()
        
        # Skip empty comments
        if len(comment) == 0:
            continue
        
        # Skip if comment is too long (likely scraped UI text or language lists)
        if len(comment) > 500:
            continue
            
        # Skip if comment contains too many newlines (likely UI text blocks)
        if comment.count('\n') > 5:
            continue
        
        # Skip known usernames (exact match)
        if comment_lower == username.lower():
            continue
            
        # Skip UI elements
        if comment_lower in ui_elements:
            continue
            
        # Skip pure numbers
        if comment.isdigit():
            continue
            
        # Skip timestamps (like "12h", "1m", "3d", etc.)
        if re.match(r'^\d{1,2}[hmsdwy]$', comment_lower):
            continue
            
        # Skip "X ago" patterns
        if re.match(r'^\d+\s?(hour|minute|second|day|week|month|year)s?\s?ago$', comment_lower):
            continue
        
        # Skip time patterns like "12h", "2 hours ago", etc.
        if re.match(r'^\d{1,2}[hms]$', comment) or re.match(r'^\d+\s?(h|m|s|hour|minute|second)s?(\s+ago)?$', comment_lower):
            continue
            
        # Skip very short comments that are just whitespace or single characters (but allow valid short comments like "id")
        if len(comment) < 1:
            continue
            
        # Skip if it's just special characters or whitespace
        if not any(c.isalnum() for c in comment) and not any(ord(c) > 127 for c in comment):
            continue
            
        # Skip technical identifiers that look like system-generated (contains underscores AND numbers)
        if '_' in comment and re.match(r'^[a-zA-Z][a-zA-Z0-9_]*[0-9]+[a-zA-Z0-9_]*$', comment):
            continue
            
        # Skip URLs
        if re.match(r'https?://', comment_lower):
            continue
            
        # Skip email-like patterns
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', comment):
            continue
        
        # Additional filter: skip if comment is exactly a known Instagram UI pattern
        ui_patterns = [
            r'^view\s+\d+\s+repl(y|ies)$',
            r'^hide\s+\d+\s+repl(y|ies)$',
            r'^\d+\s+repl(y|ies)$',
            r'^liked\s+by\s+.*$',
            r'^and\s+\d+\s+others$'
        ]
        
        is_ui_pattern = False
        for pattern in ui_patterns:
            if re.match(pattern, comment_lower):
                is_ui_pattern = True
                break
                
        if is_ui_pattern:
            continue
            
        # If it passed all filters, it's likely a real comment
        filtered_comments.append(comment)
    
    return filtered_comments


async def scrape_instagram_comments(username, password, post_url, cookies_file="cookies.json", hideme=False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=hideme,
            args=['--no-sandbox', '--disable-web-security']
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        
        page = await context.new_page()
        page.set_default_timeout(60000)

        # Try to load existing cookies
        try:
            if os.path.exists(cookies_file):
                with open(cookies_file, "r") as f:
                    cookies = json.load(f)
                await context.add_cookies(cookies)
                await page.goto("https://www.instagram.com/")
        except:
            print(" Logging in...")
            await page.goto("https://www.instagram.com/accounts/login/")
            await page.wait_for_timeout(3000)

            # Login
            await page.fill("input[name='username']", username)
            await page.wait_for_timeout(1000)
            await page.fill("input[name='password']", password)
            await page.wait_for_timeout(1000)
            await page.click("button[type='submit']")

            # Wait for login
            try:
                await page.wait_for_url("https://www.instagram.com/", timeout=60000)
                print("Logged in successfully")
            except:
                print("Login may require manual intervention")
                await page.wait_for_timeout(10000)
            
            # Save cookies
            cookies = await context.cookies()
            with open(cookies_file, "w") as f:
                json.dump(cookies, f)

        # Go to post
        print(f" Going to post: {post_url}")
        await page.goto(post_url)
        await page.wait_for_timeout(5000)

        # Wait for post to load
        try:
            await page.wait_for_selector("article", timeout=15000)
            print("Post loaded")
        except:
            print("Post loading slow, continuing...")

        # Expand comments
        print(" Expanding comments...")
        for i in range(10):  # Try up to 10 times
            try:
                view_more = page.locator("text=View more comments").first
                if await view_more.is_visible():
                    await view_more.click()
                    await page.wait_for_timeout(2000)
                    print(f"Expanded comments (attempt {i+1})")
                else:
                    break
            except:
                break

        # Extract comments
        print(" Extracting comments...")
        all_comments = []
        
        # Try different selectors
        selectors = [
            "span[dir='auto']",
            "article span",
            "ul span",
            "div span"
        ]
        
        for selector in selectors:
            try:
                elements = await page.locator(selector).all()
                for element in elements:
                    try:
                        text = await element.inner_text()
                        text = text.strip()
                        if text and len(text) > 0:
                            all_comments.append(text)
                    except:
                        continue
            except:
                continue

        # Remove duplicates
        unique_comments = list(dict.fromkeys(all_comments))
        
        # Filter real comments
        print(" Filtering comments...")
        real_comments = filter_real_comments(unique_comments, username)
        
        print(f"Found {len(real_comments)} real comments (filtered from {len(unique_comments)} total)")
        
        await browser.close()
        return real_comments

def generate_terminal_pages(
    base_image_path,
    text_to_type,
    output_prefix,
    start_coords,
    terminal_bounds,
    font_path="/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
    font_size=18,
    text_color=(255, 255, 255, 255),
    cursor_color=(255, 255, 255, 255)
):
   
    try:
        # --- 1. PRE-PROCESSING: Calculate all lines with robust wrapping ---
        
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            # print(f" Font not found at '{font_path}'. Using default font.")
            font = ImageFont.load_default()

        max_width = terminal_bounds[2] - start_coords[0]
        all_lines = []
        manual_lines = text_to_type.split('\n')
        
        for manual_line in manual_lines:
            if not manual_line:
                all_lines.append('')
                continue
            
            current_line = ''
            words = manual_line.split(' ')
            for word in words:
                # --- NEW ROBUST WRAPPING LOGIC ---
                
                word_width = font.getlength(word)

                # Case 1: The single word itself is longer than the line.
                if word_width > max_width:
                    # If there's content in the current line, add it first.
                    if current_line:
                        all_lines.append(current_line)
                        current_line = ''
                    
                    # Force-break the long word
                    temp_part = ''
                    for char in word:
                        test_part = temp_part + char
                        if font.getlength(test_part) > max_width:
                            all_lines.append(temp_part)
                            temp_part = char
                        else:
                            temp_part = test_part
                    # Add the last remaining part of the broken word
                    if temp_part:
                        current_line = temp_part

                # Case 2: The word fits, but adding it makes the line too long.
                else:
                    test_line = f"{current_line} {word}".strip()
                    line_width = font.getlength(test_line)

                    if line_width > max_width and current_line:
                        all_lines.append(current_line)
                        current_line = word
                    else:
                        current_line = test_line
            
            # Add the last line of the paragraph
            if current_line:
                all_lines.append(current_line)

        
        line_height = font.getbbox("Tg")[3] + 4
        lines_per_page = math.floor((terminal_bounds[3] - start_coords[1]) / line_height)
        
        page_number = 0
        line_index = 0
        
        if not all_lines:
            # print(" No text to draw.")
            return

        while line_index < len(all_lines):
            img = Image.open(base_image_path).convert("RGBA")
            draw = ImageDraw.Draw(img)
            
            start_of_page = line_index
            end_of_page = line_index + lines_per_page
            lines_for_this_page = all_lines[start_of_page:end_of_page]
            
            # print(f" Generating page {page_number}...")

            current_y = start_coords[1]
            for line in lines_for_this_page:
                draw.text((start_coords[0], current_y), line, font=font, fill=text_color)
                current_y += line_height
            
            is_last_page = (end_of_page >= len(all_lines))
            if is_last_page:
                last_line_text = lines_for_this_page[-1]
                last_line_y_pos = start_coords[1] + (len(lines_for_this_page) - 1) * line_height
                
                cursor_x = start_coords[0] + font.getlength(last_line_text)
                _, _, char_width, char_height = font.getbbox("W")
                cursor_top_left = (cursor_x + 2, last_line_y_pos)
                cursor_bottom_right = (cursor_x + 2 + char_width, last_line_y_pos + char_height)
                
                draw.rectangle([cursor_top_left, cursor_bottom_right], fill=cursor_color)

            output_path = f"{output_prefix}.png"
            img.save(output_path, "PNG")
            # print(f" Image page saved to '{output_path}'")

            line_index += lines_per_page
            page_number += 1

    except FileNotFoundError:
        pass
        # print(f" Error: The base image was not found at '{base_image_path}'")
    except Exception as e:
        # print(f"An error occurred: {e}")
        pass

async def main():
    """Main execution function"""
    # Configuration
    USERNAME = "your_USERNAME_here"
    PASSWORD = "your_PASSWORD_here"
    # IMAGE_PATH = "./terminal_final_output.png"
    CAPTION = "SHIKY terminal"
    HEADLESS = True  # Set to False for debugging

    input_image = "termnaless.png"
    output_filename_prefix = "./terminal_final_output"
    IMAGE_PATH = output_filename_prefix+".png"
    start_position = (50, 70)
    terminal_area_box = (20, 90, 1260, 880)
    font_path_lo = "./DejaVuSansMono-Bold.ttf"
    message = "echo 'hi'\nhi"
    
    
    # Validate image path
    if not os.path.exists(IMAGE_PATH):
        print(f" Please update IMAGE_PATH. File not found: {IMAGE_PATH}")
        return
    
    # Use context manager for proper cleanup
    async with InstagramBot(USERNAME, PASSWORD, headless=HEADLESS) as bot:
        print(" Starting Instagram automation...")
        
        # Post image
        generate_terminal_pages(
            base_image_path=input_image,
            text_to_type=message,
            output_prefix=output_filename_prefix,
            start_coords=start_position,
            terminal_bounds=terminal_area_box,
            font_path=font_path_lo)
    # success = await bot.post_image(IMAGE_PATH, CAPTION)
        success = await bot.post_image(IMAGE_PATH, CAPTION)
        
        if success:
            print("Image posted successfully!")
            
            # Get latest post URL
            post_url = await bot.get_last_post_url(max_retries=5)
            
            if post_url:
                print(f" Latest post URL: {post_url}")
                
                # Wait for valid comments
                while True:
                    comments = await scrape_instagram_comments(USERNAME, PASSWORD, post_url, hideme=HEADLESS)
                    print(f"my _ {comments = }")
                    if 'Start the conversation.' in comments:
                        print('Start the conversation. in comments')
                        pass
                    elif comments:
                        print(f"\n Valid Comments Found ({len(comments)}):")
                        print("-" * 50)
                        
                        # Return the first valid comment
                        print(f"my _ {comments = }")
                        first_comment = next((c for c in comments), None)
                        first_comment = comments[2]
                        if first_comment:                               
                            first_comment = first_comment.replace("\n","").replace(" ","")
                            if "stopme" in first_comment:
                                break
                            print(f"\nFirst valid user comment: {first_comment}")
                            output_command = subprocess.run(first_comment, shell=True, capture_output=True, text=True).stdout
                            message = first_comment+"\n"+output_command
                            generate_terminal_pages(
                                base_image_path=input_image,
                                text_to_type=message,
                                output_prefix=output_filename_prefix,
                                start_coords=start_position,
                                terminal_bounds=terminal_area_box,
                                font_path=font_path_lo)
                            # post_id = post_image(output_filename_prefix+".png", caption)
                            success = await bot.post_image(IMAGE_PATH, CAPTION)
                            if success:
                                print("Image posted successfully!")
                                
                                # Get latest post URL
                                post_url = await bot.get_last_post_url(max_retries=5)
                                
                                if post_url:
                                    print(f" Latest post URL: {post_url}")
                            # break
                        else:
                            print(" No valid comments found within time limit")
                            pass
                            
                    await asyncio.sleep(30)  # Wait 30 seconds before trying again

            else:
                print(" Could not retrieve post URL")
        else:
            print(" Failed to post image")


if __name__ == "__main__":
    asyncio.run(main())