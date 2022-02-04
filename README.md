# canvasgradecheck

A command line program to retrieve grades from Canvas LMS. This is written specifically for use within my workplace and will likely not function unless you have similar account permissions and canvas set up. The goal is for this to be user-friendly for non-tech saavy people. Students are entered manually into a csv spreadsheet (with Excel) and the rest should be handled by the program. This is a frustratingly hacky program out of necessity and is a work in progress.

## To Do

- remove use of canvasapi; just use requests instead
- scrape courses from web so they don't need to be manually entered (API doesn't work here)
    - How to work with terms?
- there are too many files, consolidate them
- deal more securely with passwords?
- for ease of use, find students by name isntead of ID; for name conflicts, see last login