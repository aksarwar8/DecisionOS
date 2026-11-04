
import pandas as pd



def prepare_product_store_data(
    features,
    test_days=28
):
    """
    Prepare product-store features using
    a chronological train-test split.
    """

    max_day = features["day_number"].max()

    cutoff_day = max_day - test_days

    train_mask = features["day_number"] <= cutoff_day
    test_mask = features["day_number"] > cutoff_day

    train = features.loc[train_mask]
    test = features.loc[test_mask]

    
    feature_columns = [
        "item_id",
        "store_id",
        "cat_id",
        "dept_id",
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "weekday",
        "month"
    ]


    target_column = "target"

    return (
        train,
        test,
        feature_columns,
        target_column
    )



def get_product_store_features(
    train,
    test,
    feature_columns,
    target_column="target"
):

    X_train = train[feature_columns]
    y_train = train[target_column]

    X_test = test[feature_columns]
    y_test = test[target_column]

    return X_train, y_train, X_test, y_test




import lightgbm as lgb


def train_product_store_lightgbm(
    X_train,
    y_train,
    X_test
):
    """
    Train a global LightGBM model
    for product-store demand forecasting.
    """

    categorical_features = [
        "item_id",
        "store_id",
        "cat_id",
        "dept_id"
    ]

    # Convert identifiers into categorical data types
    for column in categorical_features:
        X_train[column] = X_train[column].astype("category")
        X_test[column] = X_test[column].astype("category")

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=31,
        random_state=42,
        verbosity=-1,
        n_jobs=-1
    )

    model.fit(
        X_train,
        y_train,
        categorical_feature=categorical_features
    )

    predictions = model.predict(X_test)

    return model, predictions

