"""Selenium driver construction for end-to-end tests.

Two modes, chosen by whether a grid is configured:

* **Grid** — when ``SELENIUM_GRID_URL`` is set, the driver is a
  ``webdriver.Remote`` attached to that hub, so the browser runs in a selenium
  node container rather than alongside the tests. This is the mode that works
  under Docker Compose, where the application container has no browser
  installed.
* **Local** — otherwise a browser is launched on this machine, resolving the
  driver binary through ``webdriver_manager``.

``SELENIUM_BROWSER`` selects chrome (the default) or firefox in both modes.

Note for grid users: the URL a test opens is resolved *by the browser*, and
inside a browser container ``localhost`` is that container, not the
application. Point tests at a host the browser can reach, such as the web or
proxy container name; ``get_host_for_selenium_testing`` honours
``SELENIUM_TARGET_URL`` for exactly that.
"""

import os

from selenium import webdriver

DEFAULT_BROWSER = "chrome"
SUPPORTED_BROWSERS = ("chrome", "firefox")


def _resolve_browser(browser: str | None) -> str:
    name = (browser or os.getenv("SELENIUM_BROWSER") or DEFAULT_BROWSER).lower()
    if name not in SUPPORTED_BROWSERS:
        raise ValueError(
            f"Unsupported browser {name!r}. Supported: {', '.join(SUPPORTED_BROWSERS)}."
        )
    return name


def _options_for(browser: str):
    if browser == "firefox":
        return webdriver.FirefoxOptions()
    return webdriver.ChromeOptions()


def _local_driver(browser: str, options):
    """Launch a browser on this machine, resolving the driver binary."""
    if browser == "firefox":
        from selenium.webdriver.firefox.service import Service
        from webdriver_manager.firefox import GeckoDriverManager

        return webdriver.Firefox(
            service=Service(GeckoDriverManager().install()), options=options
        )

    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=options
    )


def initialize_driver(browser: str | None = None):
    """Return a WebDriver, attached to the grid when one is configured.

    Args:
        browser: "chrome" or "firefox". Defaults to $SELENIUM_BROWSER, then to
            chrome.
    """
    browser = _resolve_browser(browser)
    options = _options_for(browser)

    grid_url = os.getenv("SELENIUM_GRID_URL")
    if grid_url:
        driver = webdriver.Remote(command_executor=grid_url, options=options)
    else:
        driver = _local_driver(browser, options)

    driver.set_page_load_timeout(30)
    driver.implicitly_wait(10)
    return driver


def close_driver(driver):
    if driver is not None:
        driver.quit()
