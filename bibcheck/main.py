import argparse
import sys

from .bibliography import Bibliography

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Parse bibcheck options")
    parser.add_argument("pdf_path", help="Path to the PDF file")

    style_group = parser.add_mutually_exclusive_group()
    style_group.add_argument("-ieee", action="store_true", help="Parse IEEE style references")
    style_group.add_argument("-acm", action="store_true", help="Parse ACM style references")
    style_group.add_argument("-siam", action="store_true", help="Parse SIAM style references")

    args = parser.parse_args(argv)

    if args.acm:
        style = "acm"
    elif args.siam:
        style = "siam"
    else:
        style = "ieee"

    bib = Bibliography()
    if bib.parse(args):
        bib.validate(args)

if __name__ == "__main__":
    main()

