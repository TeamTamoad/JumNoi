from timeit import repeat

if __name__ == "__main__":
    setup_statement = """import calendar\nimport itertools"""
    repeat_number = 50000
    statement_a = """month_name = "|".join(itertools.chain(calendar.month_abbr, calendar.month_name))"""
    statement_b = """month_name = "|".join(calendar.month_abbr) + "|" + "|".join(calendar.month_name)"""
    statement_c = """month_name = f"{'|'.join(calendar.month_abbr)}|{'|'.join(calendar.month_name)}" """

    time_a = repeat(statement_a, setup_statement, number=repeat_number, repeat=1)
    time_b = repeat(statement_b, setup_statement, number=repeat_number, repeat=1)
    time_c = repeat(statement_c, setup_statement, number=repeat_number, repeat=1)

    print(f"{time_a}")
    print(f"{time_b}")
    print(f"{time_c}")
