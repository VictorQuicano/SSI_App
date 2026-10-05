"""Experiment C comparison: VON Indy C1--C3, 30 real ledger operations each."""
import json, os, time, hashlib
from pathlib import Path
import requests

RUNS = int(os.getenv("VON_C_RUNS", "30"))
RUN_ID = os.getenv("VON_C_RUN_ID", time.strftime("paper-von-c-%Y%m%dT%H%M%SZ", time.gmtime()))
VON = "http://127.0.0.1:9000"
ISSUER = "http://127.0.0.1:8131"
OUT = Path(__file__).resolve().parent / "results" / RUN_ID
OUT.mkdir(parents=True, exist_ok=True)

def ms(): return time.perf_counter_ns() / 1_000_000
def req(method, url, **kw):
    r = requests.request(method, url, timeout=30, **kw); r.raise_for_status(); return r.json()
def poll(url, predicate, timeout=30):
    start = ms()
    while ms() - start < timeout * 1000:
        try:
            value = req("GET", url)
            if predicate(value): return value, ms() - start
        except requests.HTTPError: pass
        time.sleep(.25)
    raise TimeoutError(url)
def summary(rows, key):
    xs=sorted([x[key] for x in rows if isinstance(x.get(key), (int,float))])
    if not xs:return None
    return {"mean":sum(xs)/len(xs),"p50":xs[(len(xs)-1)//2],"p95":xs[min(len(xs)-1, int(len(xs)*.95+0.999)-1)],"min":xs[0],"max":xs[-1]}

def main():
    c1w=[]; c1r=[]; c2w=[]; c2r=[]; c3w=[]; c3r=[]; schemas=[]
    for i in range(1,RUNS+1):
        seed=hashlib.sha256(f"{RUN_ID}-did-{i:02d}".encode()).hexdigest()[:32]
        t=ms(); d=req("POST", VON+"/register", json={"seed":seed,"alias":f"{RUN_ID}-did-{i:02d}","role":"ENDORSER"}); c1w.append({"index":i,"did":d["did"],"write_ms":ms()-t,"success":True})
        t=ms(); got, _=poll(VON+"/ledger/domain?query="+d["did"], lambda x: any(r.get("txn",{}).get("data",{}).get("dest")==d["did"] for r in x.get("results",[]))); c1r.append({"index":i,"did":d["did"],"read_ms":ms()-t,"success":True})
    for i in range(1,RUNS+1):
        name=f"user_credential_{RUN_ID}_{i:02d}"; body={"schema_name":name,"schema_version":"2.0","attributes":["fecha_nacimiento","nombres","can_ride","apellidos"]}
        raw=json.dumps(body, separators=(",",":")); t=ms(); d=req("POST",ISSUER+"/schemas",json=body); sid=d.get("schema_id") or d.get("sent",{}).get("schema_id"); c2w.append({"index":i,"schema_id":sid,"write_ms":ms()-t,"json_bytes":len(raw.encode()),"success":bool(sid)})
        t=ms(); got,_=poll(ISSUER+"/schemas/"+sid,lambda x: x.get("schema",{}).get("id")==sid); c2r.append({"index":i,"schema_id":sid,"read_ms":ms()-t,"success":got["schema"]["attrNames"]==body["attributes"]}); schemas.append(sid)
    for i,sid in enumerate(schemas,1):
        body={"schema_id":sid,"tag":f"{RUN_ID}-{i:02d}","support_revocation":False}; t=ms(); d=req("POST",ISSUER+"/credential-definitions",json=body); cid=d.get("credential_definition_id") or d.get("sent",{}).get("credential_definition_id"); c3w.append({"index":i,"cred_def_id":cid,"schema_id":sid,"write_ms":ms()-t,"success":bool(cid)})
        t=ms(); got,_=poll(ISSUER+"/credential-definitions/"+cid,lambda x: x.get("credential_definition",{}).get("id")==cid); cd=got["credential_definition"]; c3r.append({"index":i,"cred_def_id":cid,"read_ms":ms()-t,"success":cd.get("type")=="CL" and bool(cd.get("value",{}).get("primary"))})
    raw={"run_id":RUN_ID,"runs":RUNS,"c1":{"writes":c1w,"reads":c1r},"c2":{"writes":c2w,"reads":c2r},"c3":{"writes":c3w,"reads":c3r}}
    sums={k:{"write":summary(raw[k]["writes"],"write_ms"),"read":summary(raw[k]["reads"],"read_ms"),"write_success":sum(x["success"] for x in raw[k]["writes"]),"read_success":sum(x["success"] for x in raw[k]["reads"])} for k in ("c1","c2","c3")}
    (OUT/"raw.json").write_text(json.dumps(raw,indent=2)); (OUT/"summary.json").write_text(json.dumps(sums,indent=2)); print(json.dumps({"out":str(OUT),"summary":sums},indent=2))
if __name__=="__main__": main()
