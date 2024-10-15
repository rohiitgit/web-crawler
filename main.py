from crawler import crawl, is_valid
from report import print_report, sort_results

def main():
    url = input('Enter a URL: ')
    depth = int(input('Enter the depth: '))

    results = crawl(url, depth)
    print_report(results)

if __name__ == '__main__':
    main()