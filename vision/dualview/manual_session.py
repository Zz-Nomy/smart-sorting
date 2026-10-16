"""Auditable manual labels for unique image pairs, not independent physical objects."""
from pathlib import Path
import hashlib,json,os,uuid
from datetime import datetime,timezone

def image_key(path):
    path=Path(path).resolve()
    try:return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:return 'unreadable:'+os.path.normcase(str(path))

class ManualSession:
    def __init__(self,log_path,model_id='unspecified'):
        self.log_path=Path(log_path);self.records={};self.selected={};self.current=None
        self.model_id=model_id
        self.busy=False;self.job=0
        if self.log_path.exists():
            for line in self.log_path.read_text(encoding='utf-8').splitlines():
                event=json.loads(line)
                if event['event'] not in {'record','correct'}:raise ValueError('Unknown audit event')
                if event.get('model_id','unspecified')==self.model_id:self.records[event['sample_key']]=event
    def select(self,view,path):
        if self.busy:raise ValueError('识别进行中，暂不能换图')
        if view not in {'top','side'}:raise ValueError('Unknown view')
        self.selected[view]=str(Path(path).resolve());self.current=None
    def start(self):
        if self.busy:raise ValueError('识别进行中')
        if set(self.selected)!={'top','side'}:raise ValueError('请选择两个视图')
        self.job+=1;self.busy=True;self.current=None
        paths=dict(self.selected);fingerprints=[image_key(paths[v]) for v in ['top','side']]
        key=hashlib.sha256(json.dumps(sorted(fingerprints)).encode()).hexdigest()
        self.pending=dict(paths=paths,fingerprints=fingerprints,sample_key=key)
        return self.job,paths
    def finish(self,job,result,error=None):
        if not self.busy or job!=self.job:return False
        snapshot=self.pending
        if [image_key(snapshot['paths'][v]) for v in ['top','side']]!=snapshot['fingerprints']:
            result=None;error='输入文件在识别期间改变，本次按失败记录'
        self.current=dict(snapshot,result=result,error=error);self.busy=False
        return True
    def record(self,expected,correct=False):
        if self.busy or self.current is None:raise ValueError('请先完成当前图片对识别')
        if self.current['result'] is not None and [image_key(self.current['paths'][v]) for v in ['top','side']]!=self.current['fingerprints']:
            raise ValueError('输入文件已改变，请重新识别后再记录')
        key=self.current['sample_key'];existing=self.records.get(key)
        if existing and not correct:raise ValueError('此图片对已记录，不重复计数；真值有误请使用更正按钮')
        if correct and not existing:raise ValueError('当前图片对尚未记录，不能更正')
        result=self.current['result']
        success=result is not None and result['status']=='candidate' and result['class_name']==expected
        event=dict(event='correct' if correct else 'record',model_id=self.model_id,event_id=str(uuid.uuid4()),time_utc=datetime.now(timezone.utc).isoformat(),sample_key=key,paths=self.current['paths'],fingerprints=self.current['fingerprints'],expected=expected,predicted=result['class_name'] if result else '__error__',status=result['status'] if result else 'error',success=bool(success),error=self.current['error'])
        # Persist before changing counters; a failed write cannot claim a saved label.
        self.log_path.parent.mkdir(parents=True,exist_ok=True)
        with self.log_path.open('a',encoding='utf-8') as stream:stream.write(json.dumps(event,ensure_ascii=False)+'\n')
        self.records[key]=event
        return event
    def statistics(self):
        n=len(self.records);correct=sum(row['success'] for row in self.records.values())
        return dict(total=n,correct=correct,success_rate=correct/n if n else None)
