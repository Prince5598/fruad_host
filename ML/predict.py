import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from math import radians, cos, sin, asin, sqrt
import joblib
import xgboost as xgb
from sklearn.base import BaseEstimator, ClassifierMixin
import shap

# ================= LOAD MODELS ONCE =================
xgb_model = xgb.Booster()
xgb_model.load_model("xgb_model.json")

rf_model = joblib.load("rf_model.pkl")

# ================= PREPROCESS =================
def preprocessData(df):
    df = df.copy()

    if 'Unnamed: 0' not in df.columns:
        df['Unnamed: 0'] = 0

    df['trans_date_trans_time'] = pd.to_datetime(df['trans_date_trans_time'], dayfirst=True)

    df['hour'] = df['trans_date_trans_time'].dt.hour
    df['day_of_week'] = df['trans_date_trans_time'].dt.dayofweek
    df['day'] = df['trans_date_trans_time'].dt.day
    df['month'] = df['trans_date_trans_time'].dt.month

    df['prev_trans_time'] = df.groupby('cc_num')['trans_date_trans_time'].shift(1)
    df['time_diff_sec'] = (df['trans_date_trans_time'] - df['prev_trans_time']).dt.total_seconds().fillna(0)

    def haversine(lat1, lon1, lat2, lon2):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        return 6371 * 2 * asin(sqrt(a))

    df['dist_trans_merch'] = df.apply(
        lambda r: haversine(r['lat'], r['long'], r['merch_lat'], r['merch_long']), axis=1
    )

    le_type = LabelEncoder()
    df['trans_type_enc'] = le_type.fit_transform(df['trannsaction_type'])

    le_city = LabelEncoder()
    df['city_enc'] = le_city.fit_transform(df['city'])


    # ================= HANDLE MISSING TRAINING FEATURES =================

# No previous transaction available at inference
    df['dist_prev_trans'] = 0.0

    # No card history available → neutral defaults
    df['avg_amt'] = df['amt']
    df['std_amt'] = 0.0
    df['trans_count'] = 1

    # Amount deviation from average
    df['amt_diff_avg'] = 0.0


    feature_order = [
    'Unnamed: 0',
    'amt',
    'lat',
    'long',
    'merch_lat',
    'merch_long',
    'hour',
    'day_of_week',
    'day',
    'month',
    'time_diff_sec',
    'dist_trans_merch',
    'dist_prev_trans',
    'avg_amt',
    'std_amt',
    'trans_count',
    'amt_diff_avg',
    'trans_type_enc',
    'city_enc'
]


    return df[feature_order]

# ================= ENSEMBLE =================
class EnsembleClassifier(BaseEstimator, ClassifierMixin):
    def __init__(self, xgb_model, rf_model, threshold=0.5):
        self.xgb_model = xgb_model
        self.rf_model = rf_model
        self.threshold = threshold

    def predict_proba(self, X):
        xgb_prob = self.xgb_model.predict(xgb.DMatrix(X))
        rf_prob = self.rf_model.predict_proba(X)[:, 1]
        combined = 0.5 * xgb_prob + 0.5 * rf_prob
        return np.vstack([1 - combined, combined]).T

# ================= INFERENCE =================
def run_inference_from_df(df):
    df_processed = preprocessData(df)
    ensemble = EnsembleClassifier(xgb_model, rf_model)

    prob = ensemble.predict_proba(df_processed)[0, 1]
    pred = int(prob >= ensemble.threshold)

    return pred, prob, ["Model-based fraud pattern detected"]
