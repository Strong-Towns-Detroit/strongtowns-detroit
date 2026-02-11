"""Scrape BZA meeting minutes PDFs from Detroit's website."""

import os
import re
import time
from urllib.parse import urljoin, urlparse, unquote

import requests
from bs4 import BeautifulSoup


def download_bza_minutes(output_dir='bza_minutes'):
    """Download all BZA meeting minutes PDFs from Detroit's website."""
    os.makedirs(output_dir, exist_ok=True)

    base_url = "https://detroitmi.gov/documents"
    params = {
        'name': '',
        'field_department_target_id': '',
        'field_department_target_id_1': 'BZA Meeting Minutes (5916)',
        'field_description_value': '',
    }

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })

    page = 0
    total_downloaded = 0

    while True:
        print(f"\nFetching page {page}...")

        current_params = params.copy()
        if page > 0:
            current_params['page'] = str(page)

        try:
            response = session.get(base_url, params=current_params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error fetching page {page}: {e}")
            break

        soup = BeautifulSoup(response.content, 'html.parser')

        doc_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/document/'):
                full_url = urljoin('https://detroitmi.gov', href)
                link_text = link.get_text(strip=True)
                doc_links.append((full_url, link_text))

        if not doc_links:
            print(f"No document links found on page {page}. Ending search.")
            break

        print(f"Found {len(doc_links)} document(s) on page {page}")

        for doc_url, doc_title in doc_links:
            try:
                print(f"\n  Processing: {doc_title}")
                print(f"    Document page: {doc_url}")

                doc_response = session.get(doc_url, timeout=30)
                doc_response.raise_for_status()

                doc_soup = BeautifulSoup(doc_response.content, 'html.parser')

                pdf_url = None
                for link in doc_soup.find_all('a', href=True):
                    href = link['href']
                    if '.pdf' in href.lower():
                        pdf_url = urljoin('https://detroitmi.gov', href)
                        break

                if not pdf_url:
                    print(f"    Warning: No PDF found on document page")
                    continue

                print(f"    PDF URL: {pdf_url}")

                filename = os.path.basename(urlparse(pdf_url).path)
                filename = unquote(filename)
                filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

                filepath = os.path.join(output_dir, filename)

                if os.path.exists(filepath):
                    print(f"    Skipping (already exists): {filename}")
                    time.sleep(0.5)
                    continue

                print(f"    Downloading: {filename}")
                pdf_response = session.get(pdf_url, timeout=30)
                pdf_response.raise_for_status()

                if pdf_response.content[:4] != b'%PDF':
                    print(f"    Warning: Downloaded file doesn't appear to be a PDF")
                    continue

                with open(filepath, 'wb') as f:
                    f.write(pdf_response.content)

                total_downloaded += 1
                print(f"    Saved to: {filepath}")

                time.sleep(1)

            except Exception as e:
                print(f"    Error processing {doc_url}: {e}")

        next_page = soup.find('a', {'rel': 'next'}) or soup.find('li', {'class': 'pager__item--next'})
        if not next_page:
            print("\nNo more pages found.")
            break

        page += 1
        time.sleep(2)

    print(f"\n{'='*50}")
    print(f"Download complete!")
    print(f"Total PDFs downloaded: {total_downloaded}")
    print(f"Files saved to: {os.path.abspath(output_dir)}")
    print(f"{'='*50}")
