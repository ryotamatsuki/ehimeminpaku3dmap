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
    def test_kanji_chome_and_latest_source(self):
        self.assertEqual(r.recognized_precision('松山市立花3-7-28','愛媛県松山市立花三丁目７番２８号'),'street')
        self.assertEqual(r.recognized_precision('今治市南大門町3-2-5','愛媛県今治市南大門町三丁目２番'),'district')
        parser=r.SourceLinks()
        parser.feed('<a href="/uploaded/attachment/190246.pdf">住宅宿泊事業に基づく届出住宅一覧（令和8年8月31日時点）</a>')
        self.assertEqual(len(parser.links),1)

    def test_current_source_utf8_without_charset(self):
        # Emulate a prefecture response where requests.text would be mojibake.
        html=(
            '<html><body><a href="/uploaded/attachment/192645.pdf">'
            '<span>住宅宿泊事業に基づく</span>'
            '<span>届出住宅一覧（令和８年８月３１日時点）</span>'
            '</a></body></html>'
        )
        response=unittest.mock.Mock()
        response.content=html.encode('utf-8')
        response.encoding='ISO-8859-1'
        response.text=response.content.decode('latin-1')
        response.url=r.PAGE
        session=unittest.mock.Mock()
        session.get.return_value=response
        url,date=r.current_source(session)
        self.assertEqual(url,'https://www.pref.ehime.jp/uploaded/attachment/192645.pdf')
        self.assertEqual(date,'2026-08-31')
        session.get.assert_called_once_with(r.PAGE,timeout=30)

    def test_current_source_selects_latest_dated_listing(self):
        html=(
            '<a href="/uploaded/attachment/111.pdf">'
            '住宅宿泊事業に基づく届出住宅一覧（令和8年6月30日時点）</a>'
            '<a href="/uploaded/attachment/222.pdf">'
            '住宅宿泊事業に基づく届出住宅一覧（令和8年8月31日時点）</a>'
        )
        response=unittest.mock.Mock(content=html.encode('utf-8'),url=r.PAGE)
        session=unittest.mock.Mock()
        session.get.return_value=response
        self.assertEqual(r.current_source(session),
                         ('https://www.pref.ehime.jp/uploaded/attachment/222.pdf','2026-08-31'))

    def test_current_source_fails_closed_when_listing_is_missing(self):
        html='<a href="/uploaded/attachment/999.pdf">住宅の図面作成例</a>'
        response=unittest.mock.Mock(content=html.encode('utf-8'),url=r.PAGE)
        session=unittest.mock.Mock()
        session.get.return_value=response
        with self.assertRaisesRegex(ValueError,'Refusing stale pinned-PDF fallback'):
            r.current_source(session)

    def test_current_source_rejects_offsite_pdf_and_missing_date(self):
        html=(
            '<a href="https://example.com/list.pdf">'
            '届出住宅一覧（令和8年8月31日時点）</a>'
        )
        response=unittest.mock.Mock(content=html.encode('utf-8'),url=r.PAGE)
        session=unittest.mock.Mock()
        session.get.return_value=response
        with self.assertRaisesRegex(ValueError,'Cannot discover'):
            r.current_source(session)
        response.content=(
            '<a href="/uploaded/attachment/192645.pdf">届出住宅一覧</a>'
        ).encode('utf-8')
        with self.assertRaisesRegex(ValueError,'Cannot parse official PDF snapshot date'):
            r.current_source(session)

    def test_gsi_locality_boundary(self):
        f=[{'geometry':{'coordinates':[132.78,33.85]},'properties':{'title':'愛媛県今治市道後町2-10-33'}}]
        self.assertIsNone(r.plausible_gsi(f,'松山市道後町2-10-33'))

if __name__=='__main__':unittest.main()
