"""Build data/sample_dirty.xlsx - a deliberately messy contact list.

Every kind of problem a real client file contains is represented here, so the
tool is tested (and demoed) against reality rather than a tidy fixture.

    python scripts/make_sample.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_dirty.xlsx"

# (Name, Email Address, Mobile No, City, Notes)
ROWS = [
    ("Rahul Sharma", "rahul.sharma@gmail.com", "9876543210", "Mumbai", "clean"),
    ("Priya Patel", "Priya.Patel@Yahoo.com", "+91 98765 43211", "Ahmedabad", "clean"),
    ("Amit Verma", "amit.verma@outlook.com", "09876543212", "Delhi", "leading zero"),
    ("Sneha Iyer", "  sneha.iyer@gmail.com  ", "91 9876543213", "Chennai", "stray spaces"),
    ("  Vikram Singh", "vikram@company.in", "98765-43214", "Jaipur", "name padding"),
    ("Neha Gupta", "neha.gupta@gmail.com", "9876543210", "Pune", "DUPLICATE phone of row 1"),
    ("Rahul Sharma", "RAHUL.SHARMA@GMAIL.COM", "9876543210", "Mumbai", "DUPLICATE email of row 1"),
    ("Karan Mehta", "karan.mehta@gmail", "9876543215", "Surat", "bad email - no TLD"),
    ("Divya Nair", "divya@@gmail.com", "9876543216", "Kochi", "bad email - double @"),
    ("Arjun Rao", "arjun.rao@", "", "Hyderabad", "bad email + missing phone"),
    ("Meera Joshi", "meera.joshi@gmail.com", "12345", "Indore", "short phone"),
    ("Rohit Kumar", "rohit.kumar@gmail.com", "98765abcde", "Lucknow", "letters in phone"),
    ("Anjali Desai", "anjali.desai@gmail.com", "", "Vadodara", "blank phone"),
    ("Sameer Khan", "", "9876543219", "Bhopal", "blank email"),
    ("Pooja Reddy", "pooja.reddy@gmail.com", "+91\u00a098765\u00a043220", "Bengaluru", "non-breaking spaces"),
    ("Nikhil Jain", "nikhil.jain@gmail.com", "9876543221", "Nagpur", "clean"),
    (None, None, None, None, None),  # entirely blank row
    ("Tanvi Shah", "tanvi.shah@gmail.com", "9876543222", "Rajkot", "clean"),
    ("Aditya Bose", "aditya.bose@gmail.com", "1234567890", "Kolkata", "phone starts with 1"),
    ("Ishita Menon", "ishita.menon@gmail.com", "9876543224", "Thiruvananthapuram", "clean"),
    ("Ravi Yadav", "ravi.yadav@rediffmail.com", "9876543225", "Patna", "clean"),
    ("Kavya Pillai", "kavya.pillai@gmail.com", "9876543226", "Thrissur", "clean"),
    ("Manish Tiwari", "manish.tiwari@gmail.com", "9876543227", "Kanpur", "clean"),
    ("Shreya Das", "shreya.das@gmail.com", "9876543228", "Guwahati", "clean"),
    ("Sahil Malhotra", "sahil.malhotra@gmail.com", "9876543229", "Chandigarh", "clean"),
    ("Ritu Agarwal", "ritu.agarwal@gmail.com", "9876543230", "Agra", "clean"),
    ("Deepak Chandra", "deepak.chandra@gmail.com", "9876543231", "Varanasi", "clean"),
    ("Nandini Rao", "nandini.rao@gmail.com", "9876543232", "Mysuru", "clean"),
    ("Siddharth Kulkarni", "siddharth.k@gmail.com", "9876543233", "Nashik", "clean"),
    ("Ananya Sen", "ananya.sen@gmail.com", "9876543234", "Howrah", "clean"),
    ("Harish Reddy", "harish.reddy@gmail.com", "9876543235", "Warangal", "clean"),
    ("Preeti Chauhan", "preeti.chauhan@gmail.com", "9876543236", "Gwalior", "clean"),
    ("Ajay Pawar", "ajay.pawar@gmail.com", "9876543237", "Kolhapur", "clean"),
    ("Sunita Devi", "sunita.devi@gmail.com", "9876543238", "Ranchi", "clean"),
    ("Farhan Sheikh", "farhan.sheikh@gmail.com", "9876543239", "Aurangabad", "clean"),
    ("Lakshmi Nair", "lakshmi.nair@gmail.com", "9876543240", "Kozhikode", "clean"),
    ("Gaurav Bhatt", "gaurav.bhatt@gmail.com", "9876543241", "Dehradun", "clean"),
    ("Swati Mishra", "swati.mishra@gmail.com", "9876543242", "Prayagraj", "clean"),
    ("Rakesh Pandey", "rakesh.pandey@gmail.com", "9876543243", "Gorakhpur", "clean"),
    ("Anita George", "anita.george@gmail.com", "9876543244", "Kottayam", "clean"),
    ("Vishal Shetty", "vishal.shetty@gmail.com", "9876543245", "Mangaluru", "clean"),
    ("Priyanka Ghosh", "priyanka.ghosh@gmail.com", "9876543246", "Siliguri", "clean"),
    ("Mohit Saxena", "mohit.saxena@gmail.com", "9876543247", "Meerut", "clean"),
    ("Chitra Iyengar", "chitra.iyengar@gmail.com", "9876543248", "Hubballi", "clean"),
    ("Ramesh Gupta", "ramesh.gupta@gmail.com", "9876543249", "Jabalpur", "clean"),
    ("Sonal Kapoor", "sonal.kapoor@gmail.com", "9876543250", "Noida", "clean"),
    ("Pankaj Dubey", "pankaj.dubey@gmail.com", "9876543251", "Raipur", "clean"),
    (None, None, None, None, None),  # entirely blank row
    ("Tanya Bhatt", "tanya.bhatt@gmail.com", "9876543252", "Udaipur", "clean"),
]

COLUMNS = ["Name", "Email Address", "Mobile No", "City", "Notes"]


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(ROWS, columns=COLUMNS)

    # Write via openpyxl so we control exactly what lands in the cells.
    wb = Workbook()
    ws = wb.active
    ws.title = "Contacts"
    ws.append(COLUMNS)
    for row in df.itertuples(index=False, name=None):
        ws.append(list(row))
    wb.save(OUT)

    print(f"wrote {OUT}  ({len(df)} rows)")
    print("Expected: 2 duplicate rows, 3 bad emails, 3 bad phones, 2 blank rows dropped.")


if __name__ == "__main__":
    main()
