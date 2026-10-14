import tempfile, json, unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import geocode_permits as gp

class TestPermitCoordinates(unittest.TestCase):
    def test_incremental_cache_and_precision(self):
        with tempfile.TemporaryDirectory() as td:
            inf=Path(td)/'names.json';out=Path(td)/'coordinates.json'
            inf.write_text(json.dumps({'facilities':[{'id':'a','address':'松山市立花3-7-28'},{'id':'b','address':'今治市南大門町3-2-5'}]},ensure_ascii=False))
            def look(a,session):
                if '立花' in a:return {'coord':[132.77,33.82],'precision':'street','geocode_title':'愛媛県松山市立花三丁目7番28号'}
                return {'coord':[133.0,34.1],'precision':'district','geocode_title':'愛媛県今治市南大門町'}
            with patch.object(gp,'geocode',side_effect=look) as mocked:
                result=gp.run(inf,out,interval=0)
                self.assertEqual(mocked.call_count,2)
                again=gp.run(inf,out,interval=0)
                self.assertEqual(mocked.call_count,2)
            self.assertEqual(result['summary']['street'],1)
            self.assertEqual(again['summary']['district'],1)
            self.assertEqual(result['coordinates']['b']['address'],'今治市南大門町3-2-5')
if __name__=='__main__':unittest.main()
