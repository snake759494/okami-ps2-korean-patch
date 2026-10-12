"""설정 시제품을 넣어 AFS 확대/후속 아카이브 이동을 검증한 뒤 임시 ISO를 삭제한다."""
from pathlib import Path
import json
from build_iso import ROOT,build

output=ROOT/'work/iso_growth_test.iso'
replacement=ROOT/'work/prototype/idoption_ko.idd'
report=build(output,{0:{804:replacement}})
assert report['changed_files']==1
assert report['size']>4279599104
assert output.resolve().parent==(ROOT/'work').resolve()
output.unlink()
report.update(prototype_only=True,temporary_iso_removed=True)
(ROOT/'work/iso_growth_verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
