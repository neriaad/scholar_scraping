#!/usr/bin/env python3.7

import datetime
import requests
import os
from bs4 import BeautifulSoup
import re
from scholarly import scholarly
import io
import argparse
import sys
from shutil import rmtree

GOOGLE_SCHOLAR_URL_PREFIX = 'https://scholar.google.com/'
REGEX_TO_FIND_AUTHOR_NAME = 'gs_ai_name"><a href="(.+?)">'
REGEX_TO_FIND_NEXT_PAGE = 'window.location=(.+?)type="button"'
EXAMPLE_URL = 'https://scholar.google.com/citations?hl=en&view_op=search_authors&mauthors=label%3Aphysics&btnG='


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Downloads authors data from Google Scholar')
    parser.add_argument('--label_url', dest='label_url', action='store', required=True, type=str,
                        help=f'URL to the first page of a certain label. For example, for the label "Physics": {EXAMPLE_URL}')
    parser.add_argument('--pages', dest='pages', action='store', required=True, type=int,
                        help='Number of pages of authors to download from specified label')
    parser.add_argument('--output_dir', dest='output_dir', action='store', required=True, type=str,
                        help='Output directory for the authors')
    parser.add_argument('--skip', dest='skip', action='store', required=False, type=int,
                        help='Number of pages of authors to skip before starting to download authors')
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', required=False, default=False,
                        help='Add this to get all prints, otherwise complete silence')

    return parser.parse_args()


class HiddenPrints:
    """
    This class ensures a safe way to silence prints
    """
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


def next_page(soup) -> str:
    # This function gets search page html, and returns link to the next search page

    result = re.findall(REGEX_TO_FIND_NEXT_PAGE, str(soup))

    next_page_link = ""
    for r in result:
        if 'after' in r:
            next_page_link = r
    if not next_page_link:
        raise ValueError('Was not able to find the link to the next page')
    next_page_link = next_page_link[1:-3]
    next_page_link = next_page_link.replace("\\x3d", '=').replace("\\x26", '&')

    return f'https://scholar.google.co.il{next_page_link}'


def get_author_id(link: str) -> str:
    # Gets link to google scholar profile and returns id of author
    return link[link.index("user=") + len("user="):]


def new_folder(path: str) -> bool:
    # Creates new folder at the input path
    try:
        # Create target Directory
        os.mkdir(path)
        print(f"Researcher {path} Created ")
    except FileExistsError:
        print(f"Researcher {path} already exists")
    except:  # Some unsolvable problem. In this case, skip to the next researcher.
        print(f"The program was not able to save the Researcher  {path}")
        return False
    return True


def get_co_authors_str(co_authors) -> str:
    authors_string = f" ({len(co_authors)}):"
    for author in co_authors:
        authors_string += f"\n{author['name']}"
    return authors_string


def get_num_of_first_10_years_citations(citations: dict) -> int:
    total = 0
    i = 0

    for val in citations.values():
        total += val
        i += 1
        if i >= 10: break

    return total


def get_num_of_citations_since_n_citations(citations: dict, n: int) -> int:
    check = 0
    total = 0
    i = 0

    for val in citations.values():
        if check >= n:
            total += val
            i += 1
            if i >= 10:
                break
            continue
        check += val

    return total


def create_profile(profile_link: str, path: str) -> bool:
    # This function gets a profile link and creates a new folder with the picture and data of the author.
    # Returns True if succeeded, False if failed.

    author_id = get_author_id(profile_link)
    author = scholarly.search_author_id(author_id)
    author = scholarly.fill(author, sections=['basics', 'indices', 'coauthors', 'counts'])

    # Create new folder:
    cur_folder_path = f"{path}\\{author['name']}"
    if not new_folder(cur_folder_path):
        return False  # Problem with researcher, skip to the next one.

    # Save authors picture:
    try:
        response = requests.get(str(author["url_picture"]))
        file = open(f"{cur_folder_path}\\Author_picture.png", "wb")
        file.write(response.content)
        file.close()
    except KeyError:
        print(f"Author {author['name']} has no picture")
    except:
        print(f"Failure while downloading data for author: {profile_link}")
        return False

    try:
        ten_year = get_num_of_first_10_years_citations(author["cites_per_year"])
        ten_year_since_100 = get_num_of_citations_since_n_citations(author["cites_per_year"], 100)
        ten_year_since_500 = get_num_of_citations_since_n_citations(author["cites_per_year"], 500)
    except:
        print(f"No citations data for current author {author['name']}, so he is deleted")
        rmtree(cur_folder_path)
        return False

    # Save other authors data:
    file1 = io.open(f"{cur_folder_path}\\Author_data.txt", "w", encoding="utf-8")
    L = ["Name: ", author["name"], "\nAffiliation: ", author["affiliation"], "\nInterests: ", str(author["interests"]),
         "\nCited by: ", str(author["citedby"]), "\nCited in the last 5 years: ", str(author["citedby5y"]),
         "\nh-index: ", str(author["hindex"]), "\ni10 index: ", str(author["i10index"]),
         "\nCo authors", get_co_authors_str(author["coauthors"]), "\nCitations per year: ",
         str(author["cites_per_year"]), "\nTotal No. of citations in the first 10 years: ", str(ten_year),
         "\nNum of citations since 100 until 10 years later: ", str(ten_year_since_100),
         "\nNum of citations since 500 until 10 years later: ", str(ten_year_since_500)]
    file1.writelines(L)
    file1.write("\nNumber of years with 0 citations: " + str(
        datetime.date.today().year - int(list(author["cites_per_year"])[-1])))
    file1.close()

    return True


def load_10_researchers(soup, output_dir: str):
    # This function creates profiles for 10 researchers from one google scholar search page
    result = re.findall(REGEX_TO_FIND_AUTHOR_NAME, str(soup))
    profile_links = []
    for postfix in result:
        profile_links.append(GOOGLE_SCHOLAR_URL_PREFIX + postfix)

    for link in profile_links:
        try:
            create_profile(link, output_dir)
        except FileNotFoundError:
            print(f"There was a problem with author: {link}")
            continue


def load_n_pages(url: str, n: int, output_dir: str) -> None:
    # This function gets the url to the first search page, and saves n pages of researchers
    for i in range(n):
        print(f"Currently scraping page number: {i + 1}")
        r = requests.get(url)
        soup = BeautifulSoup(r.content, 'html.parser')
        load_10_researchers(soup, output_dir)
        url = next_page(soup)


def skip_n_pages(url: str, n: int, k: int, output_dir: str) -> None:
    # skips n pages and then starts loading authors for k pages
    for i in range(n):
        print(f"Currently skipping page number: {i + 1}")
        r = requests.get(url)
        soup = BeautifulSoup(r.content, 'html.parser')
        url = next_page(soup)
    load_n_pages(url, k, output_dir)


def main(label_url: str, pages: int, output_dir: str, skip: int = None, verbose: bool = False) -> None:
    if verbose:
        if not args.skip:
            load_n_pages(label_url, pages, output_dir)
        else:
            skip_n_pages(label_url, skip, pages, output_dir)
    else:
        with HiddenPrints():
            if not skip:
                load_n_pages(label_url, pages, output_dir)
            else:
                skip_n_pages(label_url, skip, pages, output_dir)


if __name__ == "__main__":
    args = parse_args()
    main(args.label_url, args.pages, args.output_dir, args.skip, args.verbose)
