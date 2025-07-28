# Approach Used For Adobe Round1A

## Overview

This project is designed to process and refine structured data, likely extracted from documents, using a modular pipeline approach. The solution is implemented in Python and leverages a series of custom modules to clean, filter, merge, and organize hierarchical information.

## Pipeline Approach

The solution uses a modular pipeline, where each module performs a specific transformation or extraction step. The typical flow is:

1. **Scraping**: Raw data is extracted from the source using `scraper.py`.
2. **Cleaning**: The data is cleaned to remove noise and inconsistencies (`cleaner.py`).
3. **Filtering**: Irrelevant data is filtered out (`filter.py`).
4. **Y-Axis and Indexing**: Elements are merged based on Y-axis alignment (`yaxis_merger.py`) and indexed for efficient access (`indexer.py`).
5. **Line Processing**: Lines are consolidated and merged (`line_consolidator.py`, `line_merger.py`)
6. **Title Extraction**: Titles are extracted (`title_extractor.py`).
7. **Header Processing**: Headers are consolidated and merged (`header_consolidator.py`, `header_merger.py`).
8. **Hierarchy Construction**: Hierarchical relationships are built and merged (`hierarchy.py`, `hierarchy_merger.py`).
9. **Output**: The final structured data is saved to the `output/` directory.

## How to Run

1. Place your input files in the `input/` directory.
2. Install dependencies: `pip install -r requirements.txt`
3. Run the pipeline: `python main.py`
4. Check results in the `output/` directory.
5. Or You Can Use Docker Commands

## Libraries Used

- **PyPDF2**: For PDF file manipulation and extraction.
- **PyMuPDF**: For working with PDF and other document formats.
- **Python Standard Library (STL)**: Modules such as `os`, `sys`, `re`, `collections`, and others are used throughout the code for file handling, regular expressions, data structures, and general utilities.
