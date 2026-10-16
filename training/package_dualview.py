"""Build a local demo archive; weights/images never get added to Git by this tool."""
from pathlib import Path
import argparse,csv,hashlib,json,shutil,subprocess,tempfile,zipfile

FILES=['vision_model.py','dataset_contract.py','manual_session.py','evaluate.py','demo.py','train.py','requirements.txt']

def build(checkpoint,examples,output):
    checkpoint=Path(checkpoint).resolve();examples=Path(examples).resolve();output=Path(output).resolve()
    if output.exists():raise ValueError('Archive already exists; use a new name to preserve history')
    if not checkpoint.is_file():raise ValueError('Missing checkpoint')
    repo=Path(__file__).resolve().parents[1];source=repo/'vision'/'dualview'
    photos=sorted(examples.glob('*_top.jpg'))
    if not photos:raise ValueError('No paired examples')
    pairs=[]
    for top in photos:
        cname=top.stem[:-4];color,shape=cname.split('_',1);side=examples/(cname+'_side.jpg')
        if not side.is_file():raise ValueError('Missing side view '+str(side))
        pairs.append(dict(top='examples/'+top.name,side='examples/'+side.name,color=color,shape=shape))
    with tempfile.TemporaryDirectory() as temp:
        stage=Path(temp)/'smart_sorting_demo';stage.mkdir()
        for name in FILES:shutil.copy2(source/name,stage/name)
        shutil.copy2(checkpoint,stage/'model.pt');(stage/'examples').mkdir()
        for row in pairs:
            for view in ['top','side']:shutil.copy2(examples/Path(row[view]).name,stage/row[view])
        with (stage/'examples.csv').open('w',encoding='utf-8-sig',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['top','side','color','shape']);writer.writeheader();writer.writerows(pairs)
        (stage/'verify_files.py').write_text('''from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent
manifest=json.loads((root/'package_manifest.json').read_text(encoding='utf-8'))
for name,digest in manifest['sha256'].items():
    path=root/name
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise SystemExit('FAIL: '+name)
print('PASS: '+str(len(manifest['sha256']))+' packaged files match recorded SHA256')
''',encoding='utf-8')
        (stage/'start_demo.cmd').write_text('@echo off\npython "%~dp0demo.py"\nif errorlevel 1 pause\n',encoding='ascii')
        (stage/'run_examples.cmd').write_text('@echo off\npython "%~dp0evaluate.py" --csv "%~dp0examples.csv" --checkpoint "%~dp0model.pt" --output "%~dp0example_results.json" --scope internal_temporal\nif errorlevel 1 pause\n',encoding='ascii')
        (stage/'运行说明.txt').write_text('''智能分拣双视图演示包

包含当前模块源码、可信本地权重、八类各一对既有样例、真值清单和校验摘要。
这是 Python 项目包，不包含 Python 解释器或完整依赖，不是免安装 EXE。

首次准备（建议 Python 3.10，独立虚拟环境）：
python -m venv .venv
.venv\\Scripts\\activate
python -m pip install -r requirements.txt
python verify_files.py

图形演示：python demo.py，或在已激活兼容环境中双击 start_demo.cmd。
样例评估：python evaluate.py --csv examples.csv --checkpoint model.pt --output example_results.json --scope internal_temporal
单对输入：python vision_model.py --top examples/red_cube_top.jpg --side examples/red_cube_side.jpg --json one_result.json
新照片可选择绝对路径，不要求物体居中；每图一个完整红/蓝目标，两图须属于同一个实物。

当前范围：红/蓝两色，立方体、圆柱、圆锥、多棱柱。未知类别和自动多目标配对未验收。
模型分数不是成功概率；有真值才统计实际完整成功率。拒识、异常或任一属性错误都不是成功。
八对示例来自旧视频的验证时段，不是独立测试，也不是同步拍摄。
不要用这八对的结果证明现场成功率。examples.csv 的颜色/形状为既有素材标签。

verify_files.py 校验包内固定文件，不校验后来生成的结果。只加载可信模型文件。
本包不调用训练、原始视频或外部图片路径即可推理；运行仍需安装兼容依赖。
仓库公开源代码不含此处权重/照片。本地演示包可交队内或评审查看，不自动对外上传。
''',encoding='utf-8-sig')
        commit=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
        manifest=dict(format_version=1,source_commit=commit,example_pairs=len(pairs),model_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),scope='existing-video demonstration, not independent test',dependency_note='Python and compatible installed dependencies required; not bundled',sha256={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file()})
        (stage/'package_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for p in sorted(stage.rglob('*')):
                if p.is_file():z.write(p,'smart_sorting_demo/'+p.relative_to(stage).as_posix())
    print(json.dumps(dict(archive=str(output),bytes=output.stat().st_size,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),example_pairs=len(pairs)),ensure_ascii=False,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint',required=True);parser.add_argument('--examples',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    build(args.checkpoint,args.examples,args.output)
