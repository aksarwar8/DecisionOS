
from lightgbm import LGBMRegressor


def train_lightgbm(features):

    features = features.copy()

    # Encode weekdays into numerical values
    weekday_mapping = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6
    }

    features["weekday"] = features["weekday"].map(
        weekday_mapping
    )

    feature_columns = [
        "lag_1",
        "lag_7",
        "lag_14",
        "rolling_mean_7",
        "weekday",
        "month"
    ]

    X = features[feature_columns]
    y = features["target"]

    # Chronological train-test split
    split_index = int(len(features) * 0.8)

    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]

    # Initialize LightGBM
    model = LGBMRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=-1,
        num_leaves=31,
        random_state=42,
        verbosity=-1
    )

    # Train
    model.fit(X_train, y_train)

    # Predict
    predictions = model.predict(X_test)

    return model, y_test, predictions
