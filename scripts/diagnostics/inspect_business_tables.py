if __name__ == "__main__":

    from sqlalchemy import inspect

    from src.decisionos.data.extract import get_engine


    engine = get_engine()
    inspector = inspect(engine)

    for table_name in ["products", "stores", "sales", "calendar"]:

        print(f"\n{'=' * 50}")
        print(f"TABLE: {table_name}")
        print("=" * 50)

        columns = inspector.get_columns(table_name)

        for column in columns:
            print(
                f"{column['name']} : {column['type']}"
            )
