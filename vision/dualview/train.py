from vision_model import *
import random,time,csv
from collections import defaultdict
from torchvision.models import MobileNet_V3_Small_Weights
random.seed(42);np.random.seed(42);torch.manual_seed(42)

def main():
    import argparse
    global ROOT
    ap=argparse.ArgumentParser(description='Train a frozen MobileNet dual-view shape head; temporal validation is only an internal check')
    ap.add_argument('--data',type=Path,required=True,help='v1 dataset directory with originals_manifest.jsonl and source_videos.json')
    ap.add_argument('--output',type=Path,default=ROOT)
    ap.add_argument('--cache',type=Path,default=ROOT/'cache')
    args=ap.parse_args();DATA=args.data.resolve();ROOT=args.output.resolve();ROOT.mkdir(parents=True,exist_ok=True)
    torch.hub.set_dir(str(args.cache.resolve()))
    start=time.time();device='cuda' if torch.cuda.is_available() else 'cpu'
    rows=[json.loads(x) for x in (DATA/'originals_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
    sources=json.loads((DATA/'source_videos.json').read_text(encoding='utf-8'));views={r['index']:('top' if r['view'].startswith('俯视') else 'side') for r in sources}
    groups=defaultdict(list)
    for r in rows:groups[r['video_id']].append(r)
    selected=[]
    for video,items in sorted(groups.items()):
        items.sort(key=lambda r:r['frame']);n=len(items)
        for i,r in enumerate(items):
            split='train' if i<int(n*.60) else ('val' if i>=int(n*.75) else 'gap')
            r.update(split=split,view=views[video]);selected.append(r)
    (ROOT/'split_manifest.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in selected),encoding='utf-8')
    net=mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.DEFAULT);net.classifier=torch.nn.Identity();net.eval().to(device)
    features=[]
    with torch.inference_mode():
        for i in range(0,len(selected),32):
            batch=selected[i:i+32];x=torch.stack([preprocess(read(DATA/r['original']))[0] for r in batch]).to(device)
            features.append(net(x).cpu())
            if i%160==0:print('features',i,len(selected),flush=True)
    features=torch.cat(features)
    indices=defaultdict(list)
    for i,r in enumerate(selected):indices[r['split'],r['class_name'],r['view']].append(i)
    def makepairs(split,count):
        out=[];ys=[];pairs=[]
        for cname in sorted({r['class_name'] for r in selected}):
            tops=indices[split,cname,'top'];sides=indices[split,cname,'side']
            for k in range(count):
                a=tops[k%len(tops)];b=sides[(k*7+k//len(tops))%len(sides)]
                out.append(torch.cat([features[a],features[b]]));ys.append(SHAPES.index(cname.split('_')[1]));pairs.append(dict(top=selected[a]['original'],side=selected[b]['original'],class_name=cname,shape=ys[-1]))
        return torch.stack(out),torch.tensor(ys),pairs
    x,y,trainpairs=makepairs('train',200);vx,vy,valpairs=makepairs('val',50)
    mean=x.mean(0);std=x.std(0).clamp(min=.1);x=(x-mean)/std;vx=(vx-mean)/std
    # Fixed regularized linear classification head; no validation-based hyperparameter search.
    head=torch.nn.Linear(x.shape[1],4).to(device);opt=torch.optim.AdamW(head.parameters(),lr=.005,weight_decay=.05)
    xx=x.to(device);yy=y.to(device)
    for step in range(350):
        head.train();opt.zero_grad();loss=torch.nn.functional.cross_entropy(head(xx),yy);loss.backward();opt.step()
    head.eval()
    with torch.no_grad():
        pred=head(vx.to(device)).argmax(1).cpu();tp=head(xx).argmax(1).cpu()
    conf=[[int(((vy==i)&(pred==j)).sum()) for j in range(4)] for i in range(4)]
    pack=dict(backbone={k:v.cpu() for k,v in net.state_dict().items()},mean=mean,std=std,weight=head.weight.detach().cpu(),bias=head.bias.detach().cpu(),shapes=SHAPES,architecture='MobileNetV3-small frozen features + concatenated top/side linear head',evaluation='weak same-video temporal holdout, not independent test')
    with (ROOT/'model.pt').open('wb') as handle:torch.save(pack,handle)
    # One real-image pair per class for the runnable demo; not synchronized exposures.
    demo=ROOT/'examples';demo.mkdir(exist_ok=True)
    for cname in sorted({p['class_name'] for p in valpairs}):
        p=next(p for p in valpairs if p['class_name']==cname)
        import shutil
        for view in ['top','side']:shutil.copy2(DATA/p[view],demo/f'{cname}_{view}.jpg')
    report=dict(model='MobileNetV3-small + dual-view linear head',device=device,training_original_frames=sum(r['split']=='train' for r in selected),validation_original_frames=sum(r['split']=='val' for r in selected),gap_frames=sum(r['split']=='gap' for r in selected),synthetic_pair_combinations_train=len(trainpairs),synthetic_pair_combinations_val=len(valpairs),unique_val_pairs=len({(p['top'],p['side']) for p in valpairs}),train_shape_accuracy=float((tp==y).float().mean()),temporal_holdout_shape_accuracy=float((pred==vy).float().mean()),confusion_matrix=conf,shape_order=SHAPES,seconds=round(time.time()-start,2),model_bytes=(ROOT/'model.pt').stat().st_size,warning='Same objects/backgrounds/videos occur in training and temporal validation. Paired frames are combined by class, not synchronized. These are correlated internal checks, NOT independent-test or competition accuracy. Unknown classes are not validated.')
    (ROOT/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'validation_pairs.json').write_text(json.dumps(valpairs,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
