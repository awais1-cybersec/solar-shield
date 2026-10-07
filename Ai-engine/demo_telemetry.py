"""Deterministic synthetic telemetry for transport/schema testing, not model validation."""
import argparse
import json
import math
import random
from telemetry import FEATURES

def records(count=60,seed=42):
    rng=random.Random(seed)
    for i in range(count):
        cycle=(math.sin(i/20)+1)/2
        voltage=500+40*cycle+rng.uniform(-2,2)
        current=1+11*cycle+rng.uniform(-.2,.2)
        attack=i >= count//2
        if attack: current*=3.5
        values=[voltage,current,230,50,voltage*current/1000*.98,.97,25+20*cycle,100+800*cycle]
        yield dict(zip(FEATURES,values),timestamp_ms=i*1000,label=int(attack))

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count",type=int,default=60)
    args=parser.parse_args()
    if args.count < 2: parser.error("count must be at least 2")
    for record in records(args.count): print(json.dumps(record))
