"""Controlled derived stress fixtures, never independent real captures or accuracy tests."""
from pathlib import Path
import argparse,sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vision'/'dualview'))
from vision_model import Recognizer,read,locate,cv2,np

def save(path,image):
    cv2.imencode('.png',image)[1].tofile(str(path))

def transform(image,kind):
    box,mask,_,_=locate(image);x1,y1,x2,y2=box
    if kind=='yellow':
        hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV);hsv[:,:,0][mask>0]=30
        return cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    if kind=='touch_edge':return image[y1:y2,x1:x2].copy()
    if kind=='multiple':
        crop=image[y1:y2,x1:x2];scale=140/max(crop.shape[:2]);crop=cv2.resize(crop,None,fx=scale,fy=scale)
        canvas=np.full((240,420,3),180,np.uint8);h,w=crop.shape[:2]
        canvas[40:40+h,20:20+w]=crop;canvas[40:40+h,240:240+w]=crop
        return canvas
    if kind=='occlusion':
        out=image.copy();out[y1:y1+(y2-y1)//3,x1:x2]=180;return out
    if kind=='blank':return np.full_like(image,180)
    raise ValueError(kind)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--examples',type=Path,required=True);ap.add_argument('--checkpoint',required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--device',default='cpu');ap.add_argument('--pairing-only',action='store_true');args=ap.parse_args()
    if args.output.exists():raise ValueError('Use a fresh output directory to preserve history')
    args.output.mkdir(parents=True);model=Recognizer(args.checkpoint,args.device);rows=[]
    def check(case,top,side,expectation,truth=None):
        try:
            result=model.predict(top,side);accepted=result['status']=='candidate';error=None
        except (ValueError,OSError,cv2.error) as exc:result=None;accepted=False;error=str(exc)
        if expectation=='nonaccept':passed=not accepted
        elif expectation=='correct_or_nonaccept':passed=not accepted or result['class_name']==truth
        else:raise ValueError(expectation)
        rows.append(dict(case=case,expectation=expectation,truth=truth,check_passed=passed,accepted=accepted,result=result,error=error))
    for topfile in sorted(args.examples.glob('*_top.jpg')):
        cname=topfile.stem[:-4];sidefile=args.examples/f'{cname}_side.jpg'
        if args.pairing_only:
            color,shape=cname.split('_',1)
            for other in sorted(args.examples.glob(color+'_*_side.jpg')):
                if other.stem[:-5]!=cname:check(cname+'__'+other.stem,topfile,other,'nonaccept')
            continue
        top=read(topfile);side=read(sidefile)
        for kind in ['yellow','touch_edge','multiple','occlusion','blank']:
            paths=[]
            for view,image in [('top',top),('side',side)]:
                path=args.output/f'{cname}_{kind}_{view}.png';save(path,transform(image,kind));paths.append(path)
            check(cname+'_'+kind,*paths,'correct_or_nonaccept' if kind=='occlusion' else 'nonaccept',cname)
        check(cname+'_identical_views',topfile,topfile,'nonaccept',cname)
    if not args.pairing_only:
        check('cross_color_views',args.examples/'red_cube_top.jpg',args.examples/'blue_cube_side.jpg','nonaccept')
        check('same_color_different_shapes',args.examples/'red_cube_top.jpg',args.examples/'red_cone_side.jpg','nonaccept')
        check('missing_view',args.output/'missing.jpg',args.examples/'red_cube_side.jpg','nonaccept')
    summary=dict(scope='controlled derived fixtures and intentionally invalid pairs, NOT independent real captures',total_checks=len(rows),checks_met=sum(r['check_passed'] for r in rows),failures=[r['case'] for r in rows if not r['check_passed']],note='Passing nonaccept means refusal/error as expected, not correct naming. Occlusion passes if correct or nonaccepted. Counts are engineering checks, not an identification success rate.',results=rows)
    (args.output/'report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='results'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
