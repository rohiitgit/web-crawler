def sort_results(results):
    result_arr = list(results.items())
    result_arr.sort(key=lambda x: x[1], reverse=True)

    return result_arr


def print_report(results):

    print("************************")
    print("********REPORT**********")
    print("************************")
    sorted_results = sort_results(results)

    for sorted_result in sorted_results:
        url = sorted_result[0]
        print(sorted_result)
        print(f"URL: {url}")

    print("************************")
    print("*****END REPORT*********")
    print("************************")


