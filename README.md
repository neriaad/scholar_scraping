# scholar_scraping
This code scrapes authors from labels of Google Scholar.
The program creates a folder per author, containing the authors image and a text file containing his details.

Usage example:
python scholar_scraping.py --label_url "https://scholar.google.com/citations?hl=en&view_op=search_authors&mauthors=label%3Aphysics&btnG=" --pages 10 --output_dir C:\Users\neria\authors_data -v
