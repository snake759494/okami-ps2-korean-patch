"""원본 ISO에서 AFS를 스트리밍 재배치한다. 최종 빌드는 번역 완료 검사를 요구한다.

이 게임의 AFS 파일명 레코드 마지막 DWORD는 파일 크기가 아니다.
파일명/날짜/미상 메타데이터는 그대로 보존하고 실제 TOC와 FST만 갱신한다.
"""
from pathlib import Path
import argparse,bisect,hashlib,json,os,struct
import afs,fst

ROOT=Path(__file__).resolve().parents[1]
SECTOR=2048
SOURCE_HASH='b0c55adb2f3d474e108466b52db895c2c92963a0f6bd55f4c1abac2c6ec02e9d'

def aligned(n):return (n+SECTOR-1)//SECTOR*SECTOR
def copy_span(src,dst,start,size):
    src.seek(start)
    while size:
        data=src.read(min(size,8*1024*1024))
        if not data:raise EOFError((start,size))
        dst.write(data);size-=len(data)

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        while chunk:=f.read(8*1024*1024):h.update(chunk)
    return h.hexdigest()

class ArchivePlan:
    def __init__(self,k,replacements):
        self.k=k;self.base=afs.AFS_LBA[k]*SECTOR
        self.entries,self.nt,raw=afs.toc(k)
        self.replacements=replacements;self.spans=[]
        for index,path in replacements.items():
            assert 0<=index<len(self.entries)
            name,offset,size=self.entries[index]
            self.spans.append((offset,aligned(size),Path(path),aligned(Path(path).stat().st_size)))
        self.spans.sort();self.ends=[];self.deltas=[];delta=0
        for offset,old,path,new in self.spans:
            assert not self.ends or offset>=self.ends[-1]
            # 교체 범위에 다음 파일이나 파일명 테이블이 겹치면 중단한다.
            assert all(not(offset<a<offset+old) for _,a,_ in self.entries)
            assert not(offset<=self.nt[0]<offset+old)
            self.ends.append(offset+old);delta+=new-old;self.deltas.append(delta)
        self.size=afs.AFS_SIZE[k]+delta
        self.new_entries=[(name,self.shift(offset),replacements[i].stat().st_size if i in replacements else size)
                          for i,(name,offset,size) in enumerate(self.entries)]
        self.new_nt=(self.shift(self.nt[0]),self.nt[1])
        assert self.size%SECTOR==0
        assert self.new_nt[0]+self.new_nt[1]<=self.size
        assert self.size<2**32

    def shift(self,pos):
        i=bisect.bisect_right(self.ends,pos)
        return pos+(self.deltas[i-1] if i else 0)

    def write(self,src,out):
        start=out.tell();cursor=0
        for offset,old,path,new in self.spans:
            copy_span(src,out,self.base+cursor,offset-cursor)
            with path.open('rb') as replacement:copy_span(replacement,out,0,path.stat().st_size)
            out.write(bytes(new-path.stat().st_size));cursor=offset+old
        copy_span(src,out,self.base+cursor,afs.AFS_SIZE[self.k]-cursor)
        end=out.tell();assert end-start==self.size
        out.seek(start+8)
        for _,offset,size in self.new_entries:out.write(struct.pack('<II',offset,size))
        out.write(struct.pack('<II',*self.new_nt));out.seek(end)
        return start

def directory_records(f,lba,size,path='/',seen=None):
    if seen is None:seen=set()
    if lba in seen:return []
    seen.add(lba);f.seek(lba*SECTOR);data=f.read(aligned(size));records=[];p=0
    while p<size:
        n=data[p]
        if not n:p=aligned(p+1);continue
        r=data[p:p+n];assert len(r)==n and n>=34
        loc,length=struct.unpack_from('<I',r,2)[0],struct.unpack_from('<I',r,10)[0]
        assert loc==struct.unpack_from('>I',r,6)[0]
        assert length==struct.unpack_from('>I',r,14)[0]
        name=r[33:33+r[32]]
        if name not in (b'\0',b'\1'):
            full=path+name.decode('ascii');records.append((lba*SECTOR+p,full,loc,length))
            if r[25]&2:records+=directory_records(f,loc,length,full+'/',seen)
        p+=n
    return records

def verify(output,plans,starts):
    checked=0
    with open(afs.ISO,'rb') as src,open(output,'rb') as dst:
        for plan,start in zip(plans,starts):
            dst.seek(start);assert dst.read(4)==b'AFS\0'
            assert struct.unpack('<I',dst.read(4))[0]==len(plan.entries)
            actual=[struct.unpack('<II',dst.read(8)) for _ in plan.entries]
            assert actual==[(o,s) for _,o,s in plan.new_entries]
            assert struct.unpack('<II',dst.read(8))==plan.new_nt
            src.seek(plan.base+plan.nt[0]);dst.seek(start+plan.new_nt[0])
            assert src.read(plan.nt[1])==dst.read(plan.nt[1]),'AFS 이름 메타데이터 변경'
            for i,(_,new_off,new_size) in enumerate(plan.new_entries):
                dst.seek(start+new_off)
                if i in plan.replacements:
                    check=open(plan.replacements[i],'rb');remaining=new_size
                else:
                    check=src;check.seek(plan.base+plan.entries[i][1]);remaining=new_size
                try:
                    while remaining:
                        n=min(remaining,8*1024*1024)
                        assert check.read(n)==dst.read(n),(plan.k,i,'파일 내용 불일치')
                        remaining-=n
                finally:
                    if check is not src:check.close()
                checked+=1
        dst.seek(3188*SECTOR);fdata=dst.read(71672)
        report=fst.audit(fdata,plans[0].new_entries+plans[1].new_entries)
        dst.seek(16*SECTOR);pvd=dst.read(SECTOR)
        sectors=Path(output).stat().st_size//SECTOR
        assert struct.unpack_from('<I',pvd,80)[0]==struct.unpack_from('>I',pvd,84)[0]==sectors
        root_lba=struct.unpack_from('<I',pvd,158)[0];root_size=struct.unpack_from('<I',pvd,166)[0]
        records=directory_records(dst,root_lba,root_size)
        for plan,start in zip(plans,starts):
            rec=next(r for r in records if r[1]==f'/_DATA{plan.k}.AFS;1')
            assert rec[2:]==(start//SECTOR,plan.size)
    return dict(afs_files_verified=checked,fst=report,iso_directory_verified=True,runtime_verified=False)

def build(output,replacements,noop=False):
    assert Path(afs.ISO).resolve()!=output.resolve()
    assert not output.exists(),f'기존 결과물을 덮어쓰지 않음: {output}'
    assert digest(afs.ISO)==SOURCE_HASH,'원본 ISO 해시 불일치'
    plans=[ArchivePlan(k,replacements.get(k,{})) for k in (0,1)]
    with open(afs.ISO,'rb') as src:
        src.seek(16*SECTOR);pvd=src.read(SECTOR)
        assert pvd[:7]==b'\x01CD001\x01'
        records=directory_records(src,struct.unpack_from('<I',pvd,158)[0],struct.unpack_from('<I',pvd,166)[0])
        assert all(pos<plans[0].base for pos,_,_,_ in records)
        assert all(loc<afs.AFS_LBA[0] or name.startswith('/_DATA') for _,name,loc,_ in records)
        src.seek(3188*SECTOR);fdata=src.read(71672)
        changes={i+(len(plans[0].entries) if plan.k else 0):path.stat().st_size
                 for plan in plans for i,path in plan.replacements.items()}
        fdata=fst.update_sizes(fdata,changes)
        with output.open('x+b') as out:
            copy_span(src,out,0,plans[0].base);starts=[]
            for k,plan in enumerate(plans):
                starts.append(plan.write(src,out))
                end=plan.base+afs.AFS_SIZE[k]
                next_start=plans[k+1].base if k+1<len(plans) else Path(afs.ISO).stat().st_size
                copy_span(src,out,end,next_start-end)
            total=out.tell();assert total%SECTOR==0
            # ISO9660의 리틀 엔디언/빅 엔디언 값을 함께 갱신한다.
            out.seek(16*SECTOR+80);out.write(struct.pack('<I',total//SECTOR)+struct.pack('>I',total//SECTOR))
            for plan,start in zip(plans,starts):
                pos,_,_,_=next(r for r in records if r[1]==f'/_DATA{plan.k}.AFS;1')
                out.seek(pos+2);out.write(struct.pack('<I',start//SECTOR)+struct.pack('>I',start//SECTOR))
                out.seek(pos+10);out.write(struct.pack('<I',plan.size)+struct.pack('>I',plan.size))
            out.seek(3188*SECTOR);out.write(fdata);out.flush();os.fsync(out.fileno())
    result=verify(output,plans,starts);result.update(size=output.stat().st_size,sha256=digest(output),changed_files=len(changes))
    if noop:assert result['sha256']==SOURCE_HASH
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test-noop',action='store_true');args=parser.parse_args()
    if args.test_noop:
        output=ROOT/'work/iso_roundtrip_test.iso'
        report=build(output,{},noop=True)
        assert output.resolve().parent==(ROOT/'work').resolve()
        output.unlink()
        report['temporary_iso_removed']=True
        destination=ROOT/'work/iso_roundtrip.json'
    else:
        import validate_translation
        validate_translation.main()
        status=json.loads((ROOT/'work/translation_validation.json').read_text(encoding='utf-8'))
        assert status['complete'],'미번역 또는 번역 오류가 남아 최종 ISO 빌드를 중단합니다.'
        visual_path=ROOT/'work/visual_validation.json'
        assert visual_path.exists(),'이미지 일본어 전수 한글화 검증 보고서가 없어 최종 ISO 빌드를 중단합니다.'
        visual=json.loads(visual_path.read_text(encoding='utf-8'))
        assert visual.get('complete') is True and visual.get('unreviewed_resources')==0 and visual.get('remaining_japanese_images')==0,'이미지 미검수 또는 일본어 이미지 잔존으로 최종 ISO 빌드를 중단합니다.'
        manifest=json.loads((ROOT/'work/build/manifest.json').read_text(encoding='utf-8'))
        assert manifest['complete'] and manifest['source_sha256']==SOURCE_HASH
        replacements={0:{},1:{}}
        for item in manifest['files']:
            path=ROOT/item['path'];assert digest(path)==item['sha256']
            replacements[item['archive']][item['index']]=path
        output=ROOT/'Ookami (Japan) [Korean].iso';report=build(output,replacements)
        destination=ROOT/'work/iso_verification.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
