
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from lightgbm import LGBMRegressor


def tune_lightgbm(features):

    features = features.copy()

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

    # Keep the final 20% as untouched test data
    split_index = int(len(features) * 0.8)

    X_train = X.iloc[:split_index]
    y_train = y.iloc[:split_index]

    X_test = X.iloc[split_index:]
    y_test = y.iloc[split_index:]

    # Time-series cross-validation
    tscv = TimeSeriesSplit(n_splits=3)

    # LightGBM model
    model = LGBMRegressor(
        random_state=42,
        verbosity=-1
    )

    # Hyperparameter search space
    param_grid = {
        "n_estimators": [100, 300],
        "learning_rate": [0.05, 0.1],
        "num_leaves": [15, 31],
        "max_depth": [-1, 10],
        "min_child_samples": [20, 50]
    }

    # Grid search
    grid_search = GridSearchCV(
        estimator=model,
        param_grid=param_grid,
        cv=tscv,
        scoring="neg_mean_absolute_error",
        n_jobs=-1,
        verbose=1
    )

    grid_search.fit(X_train, y_train)

    # Best model
    best_model = grid_search.best_estimator_

    # Evaluate on untouched test set
    predictions = best_model.predict(X_test)

    print("\nBest Parameters:")
    print(grid_search.best_params_)

    print("\nBest Cross-Validation MAE:")
    print(-grid_search.best_score_)

    return best_model, y_test, predictions
