"""One labelled row is one target task. Unknowns and input failures are never dropped."""
from vision_model import *
import csv,time,argparse,hashlib,os
from collections import Counter

SCOPES=['external_unverified','internal_temporal','derived_stress']

def load_evaluation_rows(csv_path):
    path=Path(csv_path).resolve()
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not {'top','side','color','shape'}.issubset(reader.fieldnames or []):raise ValueError('CSV needs top,side,color,shape columns')
        rows=list(reader)
    if not rows:raise ValueError('CSV has no tasks')
    seen_pairs=set();seen_ids=set()
    for number,row in enumerate(rows,2):
        if None in row:raise ValueError(f'Row {number}: extra CSV fields')
        for key in ['top','side','color','shape']:
            if not row.get(key) or not row[key].strip():raise ValueError(f'Row {number}: missing {key}')
            row[key]=row[key].strip()
        for key in ['top','side']:row[key]=str((path.parent/row[key]).resolve())
        key=tuple(sorted(os.path.normcase(row[v]) for v in ['top','side']))
        if key[0]==key[1]:raise ValueError('Top/side must not be the same image')
        if key in seen_pairs:raise ValueError('Duplicate image pair (including path aliases or swapped views)')
        seen_pairs.add(key)
        pair_id=(row.get('pair_id') or '').strip()
        if pair_id:
            if pair_id in seen_ids:raise ValueError('Duplicate pair_id')
            seen_ids.add(pair_id)
    return rows


def summarize(results):
    known=[r for r in results if r['known_truth']];unknown=[r for r in results if not r['known_truth']]
    accepted=[r for r in results if r['accepted']];correct=sum(r['success'] for r in results)
    review=sum(r['outcome']=='review' for r in results);errors=sum(r['outcome']=='input_error' for r in results)
    conf={};per_class={};reasons=Counter()
    for row in results:
        truth=row['expected'];conf.setdefault(truth,{})
        conf[truth][row['predicted']]=conf[truth].get(row['predicted'],0)+1
        item=per_class.setdefault(truth,dict(total=0,correct=0,accepted=0,review=0,input_errors=0,color_errors=0,shape_errors=0))
        item['total']+=1;item['correct']+=int(row['success']);item['accepted']+=int(row['accepted'])
        item['review']+=int(row['outcome']=='review');item['input_errors']+=int(row['outcome']=='input_error')
        item['color_errors']+=int(row['accepted'] and row['color_error']);item['shape_errors']+=int(row['accepted'] and row['shape_error'])
        reasons.update(row['failure_reasons'])
    for item in per_class.values():
        item['success_rate']=item['correct']/item['total']
        item['acceptance_coverage']=item['accepted']/item['total']
        item['accepted_precision']=item['correct']/item['accepted'] if item['accepted'] else None
    n=len(results)
    return dict(total=n,correct=correct,success_rate=correct/n if n else None,
        accepted=len(accepted),accepted_precision=correct/len(accepted) if accepted else None,
        acceptance_coverage=len(accepted)/n if n else None,review=review,errors=errors,
        review_or_error_rate=(review+errors)/n if n else None,
        known_tasks=len(known),known_correct=sum(r['success'] for r in known),
        known_success_rate=sum(r['success'] for r in known)/len(known) if known else None,
        unknown_tasks=len(unknown),unknown_false_accepts=sum(r['accepted'] for r in unknown),
        unknown_false_accept_rate=sum(r['accepted'] for r in unknown)/len(unknown) if unknown else None,
        unknown_success_note='Unknown rejection is reported separately; it is not a successful color+shape classification',
        per_class=per_class,confusion=conf,failure_reasons=dict(reasons),
        uncertainty='No confidence interval: independence of physical objects/capture sessions is not established')


def evaluate(csv_path,checkpoint=None,device='cpu',warmup=2,scope='external_unverified'):
    if scope not in SCOPES or warmup<0:raise ValueError('Invalid scope or warmup count')
    rows=load_evaluation_rows(csv_path)
    started=time.perf_counter();model=Recognizer(checkpoint,device);load_ms=(time.perf_counter()-started)*1000
    def synchronize():
        dev=getattr(model,'device',None)
        if dev is not None and dev.type=='cuda':torch.cuda.synchronize(dev)
    first_ms=None;warmup_errors=[]
    for i in range(warmup):
        synchronize();start=time.perf_counter()
        try:model.predict(rows[0]['top'],rows[0]['side'])
        except (ValueError,OSError,cv2.error) as e:warmup_errors.append(str(e))
        synchronize()
        if i==0:first_ms=(time.perf_counter()-start)*1000
    results=[];latencies=[]
    for row in rows:
        known=row['color'] in ['red','blue'] and row['shape'] in model.shapes
        true=row['color']+'_'+row['shape'];out=None;error=None
        synchronize();start=time.perf_counter()
        try:out=model.predict(row['top'],row['side'])
        except (ValueError,OSError,cv2.error) as e:error=str(e)
        synchronize();elapsed=(time.perf_counter()-start)*1000;latencies.append(elapsed)
        accepted=out is not None and out['status']=='candidate'
        success=known and accepted_match(out,true)
        outcome='input_error' if error is not None else ('review' if not accepted else ('success' if success else 'wrong_accept'))
        reasons=[]
        color_error=out is not None and out['color']!=row['color']
        shape_error=out is not None and out['shape']!=row['shape']
        if error is not None:reasons.append('input_error')
        elif not accepted:reasons.extend(out.get('issues') or ['review'])
        else:
            if not known:reasons.append('unknown_false_accept')
            if color_error:reasons.append('wrong_color')
            if shape_error:reasons.append('wrong_shape')
        results.append(dict(pair_id=row.get('pair_id'),physical_object_id=row.get('physical_object_id'),session_id=row.get('session_id'),top=row['top'],side=row['side'],expected=true,known_truth=known,accepted=accepted,predicted=out['class_name'] if accepted else '__'+outcome+'__',success=bool(success),outcome=outcome,color_error=color_error,shape_error=shape_error,failure_reasons=reasons,error=error,result=out,latency_ms=round(elapsed,3)))
    stats=summarize(results)
    groups={key:len({r[key] for r in results if r[key]}) for key in ['physical_object_id','session_id']}
    checkpoint_path=Path(checkpoint or ROOT/'model.pt')
    return dict(label='single_target_labelled_pair_evaluation_v2',scope=scope,
        scope_note='Pairing/physical identity and independent capture are NOT automatically verified; no multi-object detection metric is implied',
        success_definition='one row = one true target; accepted AND correct color AND correct shape; missing/review/errors remain in denominator',
        **stats,groups=groups,input_manifest_sha256=hashlib.sha256(Path(csv_path).read_bytes()).hexdigest(),
        model_sha256=hashlib.sha256(checkpoint_path.read_bytes()).hexdigest() if checkpoint_path.is_file() else None,
        timing=dict(device=str(device),load_ms=round(load_ms,3),warmup_attempts=warmup,warmup_errors=warmup_errors,first_warmup_prediction_ms=round(first_ms,3) if first_ms is not None else None,
            evaluated_mean_ms=round(float(np.mean(latencies)),3),evaluated_p50_ms=round(float(np.percentile(latencies,50)),3),evaluated_p95_ms=round(float(np.percentile(latencies,95)),3),
            note='Includes image I/O, preprocessing and inference; GPU synchronized. Model load and warmup excluded from evaluated distribution; no camera/robot time.'),results=results)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--csv',required=True);ap.add_argument('--checkpoint');ap.add_argument('--output',default='evaluation.json');ap.add_argument('--device',default='cpu');ap.add_argument('--warmup',type=int,default=2);ap.add_argument('--scope',choices=SCOPES,default='external_unverified');args=ap.parse_args()
    result=evaluate(args.csv,args.checkpoint,args.device,args.warmup,args.scope);Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='results'},ensure_ascii=False,indent=2))
