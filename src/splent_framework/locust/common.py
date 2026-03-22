import logging

from faker import Faker
from bs4 import BeautifulSoup

fake = Faker()
logger = logging.getLogger(__name__)


def get_csrf_token(response):
    soup = BeautifulSoup(response.text, "html.parser")
    token_tag = soup.find("input", {"name": "csrf_token"})
    if token_tag is None:
        logger.debug("CSRF token not found. Response HTML: %s", response.text)
        raise ValueError("CSRF token not found in the response")
    return token_tag["value"]
