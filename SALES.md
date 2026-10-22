# Selling this service

The code is the easy half. What sells is a 60-second before/after demo, because
the buyer does not want a script — they want their spreadsheet fixed.

## The one thing to get right

Never lead with "I will write a Python script". Lead with the outcome:

> I clean and validate your Excel contact list — remove duplicates, fix invalid
> emails and phone numbers, and send back a report showing exactly what changed.

The **Report** sheet is the differentiator. Competitors return a file. You return
a file plus an audit trail, which is why it looks like a professional service
rather than a favour.

## Three offers

| Offer | Price (IN) | Price (intl.) | What they get |
|---|---|---|---|
| **One-off clean** | ₹500–1,500 | $10–25 | One file cleaned, report included, 24h turnaround |
| **Custom script** | ₹3,000–6,000 | $50–100 | The tool configured for their columns, README, so they can rerun it monthly |
| **Monthly retainer** | ₹2,000–3,500 /mo | $30–50 /mo | "Send me the file each month, I return it clean" |

Start with the one-off. It is the fastest yes, and the files you receive become
your test cases. Move buyers to the script once they have sent the same file
format twice. The retainer only works after two or three delivered jobs.

## The demo

1. Keep `data/sample_dirty.xlsx` (or better, a real client file with names
   changed) and `output/sample_cleaned.xlsx`.
2. Screen-record opening the dirty file, scrolling the messy rows, then run the
   tool and open the **Report** sheet. End on the Rejected sheet: "and here is
   every row I removed, and why."
3. 60–90 seconds, no voice-over needed, captions only. This is the asset you
   attach to every proposal.

Run it again on the buyer's own file before quoting. Ten seconds of work, and
your quote is suddenly about *their* data instead of a generic service.

## Where to list

- **Fiverr / Upwork** — "Excel data cleaning and duplicate removal" is a
  high-volume search. Price low, deliver fast, then raise after 5 reviews.
- **LinkedIn** — post the 60-second demo, not the code. Small business owners
  and ops managers scroll it.
- **Local** — coaching institutes, clinics, real-estate offices and event
  organisers all live in spreadsheets with duplicate leads. One clean file for
  free, then charge.

## Qualifying questions

Ask these before quoting; they set the price and prevent surprises:

1. How many rows, and how many files per month?
2. What do the email and phone column headers say exactly?
3. Which country are the phone numbers from?
4. Is a blank email a mistake to remove, or allowed?
5. Do you want the cleaned file only, or the tool so you can rerun it?

Question 5 is where the ₹500 job becomes the ₹5,000 job.

## Raising your rate

After each job, add the client's file shape to `tests/` as a case. Once five
real files pass, you have handled almost every mess a spreadsheet contains — and
you can charge for that certainty instead of your time.

## What not to promise

No "100% accurate email verification" — this tool checks syntax, not whether a
mailbox exists. Say "format validation", and offer real verification as a
separate paid step with a paid API. Overpromising here is how you get refunds.
