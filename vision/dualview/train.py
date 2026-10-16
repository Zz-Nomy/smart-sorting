from vision_model import *
from dataset_contract import load_pairs, validate_shapes
import argparse, random, time, hashlib, shutil, subprocess
from collections import defaultdict
from torchvision.models import MobileNet_V3_Small_Weights


def main():
    ap=argparse.ArgumentParser(description='Train dual-view head from audited real pairs, or explicitly opt into weak legacy checks')
    inputs=ap.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--pairs',type=Path,help='Explicit paired CSV with object/session/parent IDs and train/val/test splits')
    inputs.add_argument('--data',type=Path,help='Legacy original-frame dataset; requires --legacy-temporal')
    ap.add_argument('--legacy-temporal',action='store_true')
    ap.add_argument('--shapes',type=Path,help='JSON list of shape identifiers; saved in checkpoint order')
    ap.add_argument('--output',type=Path,default=ROOT)
    ap.add_argument('--cache',type=Path,default=ROOT/'cache')
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--steps',type=int,default=350)
    ap.add_argument('--overwrite',action='store_true',help='Explicitly allow replacing an existing output model')
    args=ap.parse_args()
    if args.steps<1:ap.error('--steps must be positive')
    if args.data and not args.legacy_temporal:ap.error('--data needs --legacy-temporal; same-video validation is not independent')
    if args.pairs and args.legacy_temporal:ap.error('--legacy-temporal is only valid with --data')
    shapes=validate_shapes(json.loads(args.shapes.read_text(encoding='utf-8-sig')) if args.shapes else SHAPES)
    out=args.output.resolve()
    if (out/'model.pt').exists() and not args.overwrite:ap.error('Output model exists; choose a new output directory or explicitly use --overwrite')
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    start=time.time();device='cuda' if torch.cuda.is_available() else 'cpu'
    legacy_rows=[]
    if args.pairs:
        pairs=load_pairs(args.pairs,shapes)
        scope='explicit_real_pairs_group_checked_metadata_not_independently_verified'
        fingerprint=hashlib.sha256(args.pairs.read_bytes()).hexdigest()
    else:
        data=args.data.resolve()
        manifest=data/'originals_manifest.jsonl'
        rows=[json.loads(line) for line in manifest.read_text(encoding='utf-8').splitlines()]
        sources=json.loads((data/'source_videos.json').read_text(encoding='utf-8'))
        views={r['index']:('top' if r['view'].startswith('俯视') else 'side') for r in sources}
        groups=defaultdict(list)
        for row in rows:groups[row['video_id']].append(row)
        indices=defaultdict(list)
        for video,items in sorted(groups.items()):
            items.sort(key=lambda r:r['frame']);n=len(items)
            for i,row in enumerate(items):
                row=dict(row,split='train' if i<int(n*.60) else ('val' if i>=int(n*.75) else 'gap'),view=views[video])
                legacy_rows.append(row)
                if row['split']!='gap':indices[row['split'],row['class_name'],row['view']].append(row)
        pairs=[]
        for split,count in [('train',200),('val',50)]:
            for cname in sorted({r['class_name'] for r in rows}):
                color,shape=cname.split('_',1)
                if color not in ['red','blue'] or shape not in shapes:raise ValueError('Unsupported legacy class '+cname)
                tops=indices[split,cname,'top'];sides=indices[split,cname,'side']
                if not tops or not sides:raise ValueError('Missing paired view for '+cname+' '+split)
                for k in range(count):
                    a=tops[k%len(tops)];b=sides[(k*7+k//len(tops))%len(sides)]
                    pairs.append(dict(top=str(data/a['original']),side=str(data/b['original']),color=color,shape=shape,split=split,pair_id=f'{split}_{cname}_{k}'))
        scope='weak_same_video_temporal_holdout_not_independent_test'
        fingerprint=hashlib.sha256(manifest.read_bytes()).hexdigest()
    active=[p for p in pairs if p['split'] in ['train','val']]
    paths=sorted({p[v] for p in active for v in ['top','side']})
    # Do not read or extract features from sealed test images.
    inputs=[]
    for path in paths:inputs.append(preprocess(read(path))[0])
    for split in ['train','val']:
        if not any(p['split']==split for p in active):raise ValueError('Missing '+split)
    if {p['shape'] for p in active if p['split']=='train'}!=set(shapes):raise ValueError('Training must cover every shape')
    out.mkdir(parents=True,exist_ok=True);torch.hub.set_dir(str(args.cache.resolve()))
    net=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT);net.classifier=torch.nn.Identity();net.eval().to(device)
    features=[]
    with torch.inference_mode():
        for i in range(0,len(inputs),32):
            features.append(net(torch.stack(inputs[i:i+32]).to(device)).cpu())
            if i%160==0:print('features',i,len(inputs),flush=True)
    lookup=dict(zip(paths,torch.cat(features)))
    def assemble(split):
        selected=[p for p in active if p['split']==split]
        x=torch.stack([torch.cat([lookup[p['top']],lookup[p['side']]]) for p in selected])
        y=torch.tensor([shapes.index(p['shape']) for p in selected])
        return x,y,selected
    x,y,trainpairs=assemble('train');vx,vy,valpairs=assemble('val')
    mean=x.mean(0);std=x.std(0).clamp(min=.1);xx=((x-mean)/std).to(device);yy=y.to(device)
    head=torch.nn.Linear(x.shape[1],len(shapes)).to(device)
    opt=torch.optim.AdamW(head.parameters(),lr=.005,weight_decay=.05)
    for _ in range(args.steps):
        opt.zero_grad();loss=torch.nn.functional.cross_entropy(head(xx),yy);loss.backward();opt.step()
    with torch.inference_mode():
        pred=head(((vx-mean)/std).to(device)).argmax(1).cpu();tp=head(xx).argmax(1).cpu()
    commit=subprocess.run(['git','-C',str(Path(__file__).resolve().parents[2]),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip() or 'unavailable'
    code_dir=Path(__file__).resolve().parent
    code_hashes={name:hashlib.sha256((code_dir/name).read_bytes()).hexdigest() for name in ['train.py','vision_model.py','dataset_contract.py']}
    dirty=bool(subprocess.run(['git','-C',str(code_dir.parents[1]),'status','--porcelain','--untracked-files=no'],capture_output=True,text=True).stdout.strip())
    metadata=dict(scope=scope,seed=args.seed,steps=args.steps,input_manifest_sha256=fingerprint,code_commit=commit,code_dirty=dirty,source_sha256=code_hashes,shapes=shapes,colors=['red','blue'],test_pairs_sealed=sum(p['split']=='test' for p in pairs))
    pack=dict(backbone={k:v.cpu() for k,v in net.state_dict().items()},mean=mean,std=std,weight=head.weight.detach().cpu(),bias=head.bias.detach().cpu(),shapes=shapes,metadata=metadata)
    with (out/'model.pt').open('wb') as handle:torch.save(pack,handle)
    for filename,items in [('training_pairs.json',trainpairs),('validation_pairs.json',valpairs)]:
        (out/filename).write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
    if legacy_rows:(out/'split_manifest.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in legacy_rows),encoding='utf-8')
    report=dict(**metadata,device=device,training_pairs=len(trainpairs),validation_pairs=len(valpairs),unique_validation_pairs=len({(p['top'],p['side']) for p in valpairs}),features_extracted_images=len(paths),train_shape_accuracy=float((tp==y).float().mean()),validation_shape_accuracy=float((pred==vy).float().mean()),confusion_matrix=[[int(((vy==i)&(pred==j)).sum()) for j in range(len(shapes))] for i in range(len(shapes))],seconds=round(time.time()-start,2),model_bytes=(out/'model.pt').stat().st_size,model_sha256=hashlib.sha256((out/'model.pt').read_bytes()).hexdigest(),warning='Metadata checks cannot verify truthful physical IDs, capture conditions, or unknown-class generalization. Legacy temporal checks are correlated and never independent tests.')
    (out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
