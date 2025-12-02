from flask import Flask, request, jsonify
import pandas as pd
import os
from datetime import datetime
from predict import run_inference_from_df

app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route('/predict', methods=['POST'])
def preprocess_predict():
    try:
        data = request.get_json()

        formatted_time = datetime.strptime(
            data['transactionTime'], '%Y-%m-%dT%H:%M'
        ).strftime('%d-%m-%Y %H:%M')

        row = {
            'trans_date_trans_time': formatted_time,
            'cc_num': data['ccNum'],
            'trannsaction_type': data['transactionType'],
            'amt': data['amount'],
            'city': data['city'],
            'lat': data['userLocation']['lat'],
            'long': data['userLocation']['lon'],
            'trans_num': data['transactionId'],
            'merch_lat': data['merchantLocation']['lat'],
            'merch_long': data['merchantLocation']['lon']
        }

        df = pd.DataFrame([row])

        predicted_class, fraud_prob, fraud_reason = run_inference_from_df(df)

        return jsonify({
            "is_fraud": bool(predicted_class),
            "confidence": float(fraud_prob),
            "fraud_reason": fraud_reason
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)
