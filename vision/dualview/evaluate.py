"""Evaluate labelled image pairs. Success requires BOTH color and shape, with no review flag."""
from vision_model import *
import csv,time,argparse

def evaluate(csv_path,checkpoint=None,device='cpu'):
    path=Path(csv_path).resolve()
    with path.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    required={'top','side','color','shape'}
    if not rows or not required.issubset(rows[0]):raise ValueError('CSV needs top,side,color,shape columns and at least one row')
    keys=[(r['top'],r['side']) for r in rows]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate image pairs would inflate statistics; deduplicate CSV first')
    model=Recognizer(checkpoint,device);results=[];conf={};correct=0;review=0;errors=0;latencies=[]
    for row in rows:
        if row['color'] not in ['red','blue'] or row['shape'] not in model.shapes:raise ValueError('Unsupported truth class: '+str(row))
        true=row['color']+'_'+row['shape'];start=time.perf_counter();out=None;error=None
        try:out=model.predict(path.parent/row['top'],path.parent/row['side'])
        except (ValueError,OSError) as e:error=str(e)
        elapsed=(time.perf_counter()-start)*1000;latencies.append(elapsed)
        accepted=out is not None and out['status']=='candidate'
        success=accepted_match(out,true)
        correct+=int(success);review+=int(out is not None and not accepted);errors+=int(error is not None)
        predicted=out['class_name'] if accepted else '__review_or_error__'
        conf.setdefault(true,{});conf[true][predicted]=conf[true].get(predicted,0)+1
        results.append(dict(top=row['top'],side=row['side'],expected=true,predicted=predicted,success=success,error=error,result=out,latency_ms=round(elapsed,2)))
    return dict(label='labelled_pair_evaluation',scope='User supplied CSV; independence is NOT automatically verified',success_definition='accepted AND correct color AND correct shape; review/errors count as unsuccessful',total=len(rows),correct=correct,success_rate=correct/len(rows),review=review,errors=errors,review_or_error_rate=(review+errors)/len(rows),mean_latency_ms=round(float(np.mean(latencies)),2),p95_latency_ms=round(float(np.percentile(latencies,95)),2),confusion=conf,results=results)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--checkpoint');ap.add_argument('--output',default='evaluation.json');ap.add_argument('--device',default='cpu');args=ap.parse_args()
    result=evaluate(args.csv,args.checkpoint,args.device);Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False,indent=2))
