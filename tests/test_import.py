import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refresh_data as r
from unittest.mock import patch

class TestImporter(unittest.TestCase):
    def test_pdf_extraction_and_counting(self):
        class FakePage:
            def get_text(self, *_args, **_kwargs):
                return '届出住宅の所在地\n松山市三番町２丁目４－３０\n今治市大三島町宮浦１０１３\n北宇和郡松野町大字松丸２４４'
        class FakeDoc:
            page_count=1
            def __iter__(self): return iter([FakePage()])
            def close(self): pass
        with patch.object(r.fitz,'open', return_value=FakeDoc()):
            addresses,anomalies=r.read_pdf(b'%PDF')
        self.assertEqual(len(addresses),3)
        self.assertEqual(r.municipality(addresses[2]),'松野町')
    def test_normalization(self):
        self.assertEqual(r.municipality('伊予郡砥部町原町 1-2'),'砥部町')
        self.assertEqual(r.basename('松山市道後町２－１０－３３ マンション202'),'松山市道後町2-10-33')
    def test_gsi_locality_boundary(self):
        f=[{'geometry':{'coordinates':[132.78,33.85]},'properties':{'title':'愛媛県今治市道後町2-10-33'}}]
        self.assertIsNone(r.plausible_gsi(f,'松山市道後町2-10-33'))

if __name__=='__main__':unittest.main()
