"""Evaluate a trusted model/scaler pair on labeled JSONL windows; never fit on test data."""
import argparse
from collections import deque
import json
from pathlib import Path
import time
from telemetry import extract_features

def metrics(labels,predictions):
    if len(labels)!=len(predictions) or not labels: raise ValueError("Nonempty, equally sized inputs required")
    tp=sum(y==1 and p==1 for y,p in zip(labels,predictions))
    fp=sum(y==0 and p==1 for y,p in zip(labels,predictions))
    tn=sum(y==0 and p==0 for y,p in zip(labels,predictions))
    fn=sum(y==1 and p==0 for y,p in zip(labels,predictions))
    return {"tp":tp,"fp":fp,"tn":tn,"fn":fn,"precision":tp/(tp+fp) if tp+fp else None,"recall":tp/(tp+fn) if tp+fn else None,"false_positive_rate":fp/(fp+tn) if fp+tn else None}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input",type=Path)
    parser.add_argument("--model",type=Path,required=True)
    parser.add_argument("--scaler",type=Path,required=True)
    parser.add_argument("--threshold",type=float,required=True)
    args=parser.parse_args()
    import numpy as np
    import joblib
    import tensorflow as tf
    if not np.isfinite(args.threshold) or args.threshold < 0: parser.error("Invalid threshold")
    model=tf.keras.models.load_model(args.model,compile=False)
    scaler=joblib.load(args.scaler)
    buffer=deque(maxlen=20); labels=[]; predictions=[]; latency=[]
    with args.input.open() as source:
        for line in source:
            row=json.loads(line)
            if row.get("label") not in (0,1): raise ValueError("Each row needs label 0 or 1")
            buffer.append((extract_features(row),row["label"]))
            if len(buffer)<20: continue
            start=time.perf_counter()
            x=np.expand_dims(scaler.transform([v for v,_ in buffer]),0)
            output=model.predict(x,verbose=0)
            if output.shape != x.shape: raise ValueError("Reconstruction shape mismatch")
            error=float(np.mean(np.square(x-output)))
            if not np.isfinite(error): raise ValueError("Non-finite reconstruction error")
            latency.append((time.perf_counter()-start)*1000)
            labels.append(int(any(y for _,y in buffer)))
            predictions.append(int(error>args.threshold))
    result=metrics(labels,predictions)
    result.update(windows=len(labels),window_label="any anomalous sample",threshold=args.threshold,mean_latency_ms=float(np.mean(latency)),p95_latency_ms=float(np.percentile(latency,95)),latency_scope="scaling plus prediction and MSE; excludes transport/storage; includes first call")
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__ == "__main__": main()
