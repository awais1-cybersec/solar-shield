"""Integration check using committed model/scaler; database delivery is captured locally."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'Ai-engine'))
os.environ.setdefault('TF_NUM_INTRAOP_THREADS','1')
os.environ.setdefault('TF_NUM_INTEROP_THREADS','1')
import joblib
import numpy as np
import tensorflow as tf
from demo_telemetry import records
from telemetry import extract_features
from evaluate import metrics
import run_inference

class CaptureWriter:
    def __init__(self): self.points=[]
    def write(self,**kwargs): self.points.append(kwargs['record'].to_line_protocol())

class CaptureDB:
    def __init__(self,*args,**kwargs): self.writer=CaptureWriter()
    def write_api(self,**kwargs): return self.writer
    def close(self): pass

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    args=argparse.Namespace(broker='localhost',topic='solarshield/telemetry/inverter1',threshold=.12,model=BASE/'Ai-engine/models/solar_shield.keras',scaler=BASE/'Ai-engine/scaler.pkl',port=1883,ca_cert=None,allow_insecure_lab=True)
    with patch.dict(os.environ,{'INFLUX_TOKEN':'local-test-placeholder','MQTT_USERNAME':'local-test','MQTT_PASSWORD':'local-test-placeholder'}),patch.object(run_inference,'InfluxDBClient',CaptureDB):
        detector=run_inference.SolarShieldRTADS(args)
    assert detector.scaler.n_features_in_==8
    assert detector.model.input_shape[1:]==(20,8)
    assert detector.model.output_shape[1:]==(20,8)
    rows=list(records(80))
    for row in rows:
        message=argparse.Namespace(payload=json.dumps(row).encode())
        detector.on_message(None,None,message)
    assert len(detector.write_api.points)==61, 'Expected one point per full sliding window'
    assert all('mse=' in point and 'is_anomaly=' in point for point in detector.write_api.points)
    before=list(detector.buffer)
    points_before=len(detector.write_api.points)
    detector.on_message(None,None,argparse.Namespace(payload=b'{invalid'))
    assert list(detector.buffer)==before
    assert len(detector.write_api.points)==points_before
    labels=[];predictions=[];errors=[];latencies=[]
    for i in range(19,len(rows)):
        x=np.expand_dims(detector.scaler.transform([extract_features(row) for row in rows[i-19:i+1]]),0)
        start=time.perf_counter();out=detector.model.predict(x,verbose=0);latencies.append((time.perf_counter()-start)*1000)
        assert out.shape==x.shape and np.isfinite(out).all()
        mse=float(np.mean(np.square(x-out)));errors.append(mse)
        labels.append(int(any(r['label'] for r in rows[i-19:i+1])))
        predictions.append(int(mse>args.threshold))
    result={'validated_at_utc':datetime.now(timezone.utc).isoformat(),'dependencies':{name:version(name) for name in ('numpy','scikit-learn','joblib','paho-mqtt','influxdb-client')},'scope':'Synthetic smoke test; not held-out real-world accuracy. MQTT network and real InfluxDB/Grafana not exercised.', 'python':platform.python_version(),'tensorflow':tf.__version__,'keras':tf.keras.__version__,'model_input_shape':list(detector.model.input_shape),'scaler_features':int(detector.scaler.n_features_in_),'feature_names_recorded':hasattr(detector.scaler,'feature_names_in_'),'records':len(rows),'windows':len(errors),'database_points_captured':len(detector.write_api.points),'threshold':args.threshold,'threshold_status':'Historical code value, not calibrated in this test','mse_min':min(errors),'mse_max':max(errors),'synthetic_metrics':metrics(labels,predictions),'warm_inference_mean_ms':float(np.mean(latencies)),'warm_inference_p95_ms':float(np.percentile(latencies,95)),'latency_scope':'Model.predict only, after first integration pass; current container CPU, not user hardware','sha256':{path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in (args.model,args.scaler)}}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
