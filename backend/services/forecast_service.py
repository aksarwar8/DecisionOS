
import pandas as pd

from backend.services.model_service import load_model


model = load_model()


def predict_demand(data):

    input_data = pd.DataFrame([{
        "item_id": data.item_id,
        "store_id": data.store_id,
        "cat_id": data.item_id.split("_")[0],
        "dept_id": data.item_id.split("_")[1],
        "lag_1": data.lag_1,
        "lag_7": data.lag_7,
        "lag_14": data.lag_14,
        "rolling_mean_7": data.rolling_mean_7,
        "weekday": data.weekday,
        "month": data.month
    }])

    categorical_features = [
        "item_id", "store_id", "cat_id", "dept_id"
    ]

    for column in categorical_features:
        input_data[column] = input_data[column].astype("category")

    prediction = model.predict(input_data)

    return float(prediction[0])
