from docx import Document
import csv
from lxml import etree

from strongtowns_detroit.parcels.docx_parser import get_cell_spans, expand_table


def extract_all_tables(doc_path):
    document = Document(doc_path)
    all_tables = []
    for idx, table in enumerate(document.tables, 1):
        expanded = expand_table(table)
        all_tables.extend(expanded)
        # Separate tables by a blank line
        all_tables.append([""] * len(expanded[0]))
    return all_tables

def write_csv(all_tables, out_path):
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(all_tables)


if __name__ == "__main__":
    input_docx = "DIVISION_1.___USE_TABLES.docx"
    output_csv = "merged_tables.csv"

    all_tables = extract_all_tables(input_docx)
    write_csv(all_tables, output_csv)
    print(f"✅ Extracted {len(all_tables)} rows to {output_csv}")
