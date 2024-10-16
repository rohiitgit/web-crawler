from crawler import crawl
from report import print_report

def main():
    url = input('Enter a URL: ')
    depth = int(input('Enter the depth: '))

    results = crawl(url, depth)
    print_report(results)
    return results

if __name__ == '__main__':
    main()
