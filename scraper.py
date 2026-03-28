"""LinkedIn job posting scraper.

Attempts to extract job details from a LinkedIn job URL.
Falls back gracefully if scraping fails (LinkedIn is aggressive about blocking).
"""

import re

import httpx
from bs4 import BeautifulSoup, NavigableString, Tag
from dataclasses import dataclass


_NOISE_PATTERNS = re.compile(
    r"(\d+\s*(applicants?|views?|clicks?))", re.IGNORECASE
)

# Tags whose inner content we keep when sanitizing HTML.
_SAFE_TAGS = frozenset({
    "p", "br", "ul", "ol", "li", "strong", "b", "em", "i",
    "h1", "h2", "h3", "h4", "h5", "h6", "span",
})


@dataclass
class JobInfo:
    """Scraped job posting data."""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    seniority_level: str = ""
    employment_type: str = ""
    job_function: str = ""
    industries: str = ""
    salary: str = ""


async def scrape_linkedin_job(url: str) -> JobInfo:
    """Scrape job details from a LinkedIn job posting URL.

    LinkedIn public job pages often have structured data we can parse.
    If scraping fails, returns defaults so the user can fill in manually.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        return _parse_job_page(soup)
    except Exception:
        return JobInfo()


def _is_noise(text: str) -> bool:
    """Return True if text is a metadata string like 'Over 200 applicants'."""
    return bool(_NOISE_PATTERNS.search(text)) or text.lower().startswith("over ")


def _parse_title_tag(soup: BeautifulSoup) -> tuple[str, str, str]:
    """Extract title, company, location from the <title> tag.

    LinkedIn uses two formats:
      - "Job Title - Company | LinkedIn"
      - "Company hiring Job Title in Location | LinkedIn"
    """
    title_tag = soup.find("title")
    if not title_tag or not title_tag.string:
        return "", "", ""

    raw = title_tag.string.split(" | ")[0].strip()

    # Format: "Company hiring Job Title in Location"
    hiring_match = re.match(
        r"^(.+?)\s+hiring\s+(.+?)\s+in\s+(.+)$", raw
    )
    if hiring_match:
        return (
            hiring_match.group(2).strip(),
            hiring_match.group(1).strip(),
            hiring_match.group(3).strip(),
        )

    # Format: "Job Title - Company"
    if " - " in raw:
        parts = raw.split(" - ", 1)
        return parts[0].strip(), parts[1].strip(), ""

    return raw, "", ""


def _parse_job_page(soup: BeautifulSoup) -> JobInfo:
    """Extract job info from parsed HTML."""
    # Start with title tag (most reliable source)
    title, company, location = _parse_title_tag(soup)
    info = JobInfo(title=title, company=company, location=location)

    # Override with structured selectors if available
    title_el = soup.select_one(
        ".top-card-layout__title, .topcard__title, h1.t-24, h1"
    )
    if title_el:
        info.title = title_el.get_text(strip=True) or info.title

    company_el = soup.select_one(
        ".topcard__org-name-link, "
        ".top-card-layout__company, "
        "a.topcard__org-name-link"
    )
    if company_el:
        info.company = company_el.get_text(strip=True) or info.company

    # Location: scan bullet-flavored spans, skip noise and company dupes
    if not info.location:
        for el in soup.select(
            ".topcard__flavor--bullet, .top-card-layout__bullet"
        ):
            text = el.get_text(strip=True)
            if (
                text
                and not _is_noise(text)
                and text.lower() != info.company.lower()
            ):
                info.location = text
                break

    # Fallback: second topcard__flavor span (index 0 = company, 1 = location)
    if not info.location:
        flavors = soup.select("span.topcard__flavor")
        for fl in flavors:
            text = fl.get_text(strip=True)
            if (
                text
                and not _is_noise(text)
                and text.lower() != info.company.lower()
            ):
                info.location = text
                break

    # Description — keep safe HTML for readable formatting
    desc_el = soup.select_one(
        ".show-more-less-html__markup, "
        ".description__text, "
        "section.description"
    )
    if desc_el:
        info.description = _sanitize_html(desc_el)

    # Job criteria (seniority, employment type, function, industries)
    _criteria_map = {
        "seniority level": "seniority_level",
        "employment type": "employment_type",
        "job function": "job_function",
        "industries": "industries",
    }
    for el in soup.select(".description__job-criteria-item"):
        header = el.select_one(".description__job-criteria-subheader")
        value = el.select_one(".description__job-criteria-text")
        if header and value:
            key = header.get_text(strip=True).lower()
            attr = _criteria_map.get(key)
            if attr:
                setattr(info, attr, value.get_text(strip=True))

    # Salary — look for dollar amounts in the plain-text description
    plain_desc = desc_el.get_text() if desc_el else ""
    if plain_desc:
        salary_match = re.search(
            r"\$[\d,]+(?:\.\d+)?\s*(?:[-\u2013\u2014]|to)\s*\$[\d,]+(?:\.\d+)?",
            plain_desc,
        )
        if salary_match:
            info.salary = salary_match.group()

    return info


def _sanitize_html(element: Tag) -> str:
    """Strip unsafe tags from HTML, keeping only formatting elements.

    Walks the tree and keeps only tags in _SAFE_TAGS.
    Unwraps (keeps children) for any other tag (like <div>, <a>, <section>).
    Returns a cleaned HTML string capped at ~3000 chars.
    """
    # Work on a copy so we don't mutate the soup
    clone = BeautifulSoup(str(element), "html.parser")

    # Strip all attributes from every tag (no class, id, style, href)
    for tag in clone.find_all(True):
        tag.attrs = {}

    # Unwrap tags that aren't in our safe list
    changed = True
    while changed:
        changed = False
        for tag in clone.find_all(True):
            if tag.name not in _SAFE_TAGS:
                tag.unwrap()
                changed = True

    # Collapse excessive whitespace / empty tags / HTML comments
    html = str(clone)
    html = re.sub(r"<!--.*?-->", "", html)  # strip comments
    html = re.sub(r"(<br\s*/?>\s*){3,}", "<br><br>", html)
    html = re.sub(r"<(p|li|span)>\s*</(p|li|span)>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)

    return html.strip()[:3000]
