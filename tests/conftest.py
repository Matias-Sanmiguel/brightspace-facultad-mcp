import pytest_asyncio
from playwright.async_api import async_playwright


@pytest_asyncio.fixture
async def page(tmp_path):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True,downloads_path=str(tmp_path))
        context = await browser.new_context(accept_downloads=True)
        p = await context.new_page()
        yield p
        await browser.close()
