import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import refine_permit_geocodes as r

class TestABR(unittest.TestCase):
 def test_number_parsing(self):
  self.assertEqual(r.parse_numbers('877-2'),('877','2'))
  self.assertEqual(r.parse_numbers('７７７番地１'),('777','1'))
  self.assertEqual(r.parse_numbers('４番２号'),('4','2'))
  self.assertIsNone(r.parse_numbers('甲507'))
  self.assertIsNone(r.parse_numbers('877-2 A棟'))
 def test_gsi_full_vs_partial_and_wrong_number(self):
  self.assertTrue(r.gsi_exact('松山市高岡町877-2','愛媛県松山市高岡町877番地2'))
  self.assertFalse(r.gsi_exact('松山市高岡町877-2','愛媛県松山市高岡町877番地'))
  self.assertFalse(r.gsi_exact('松山市高岡町877-2','愛媛県松山市高岡町877番地20'))
  self.assertFalse(r.gsi_exact('松山市福角町甲1233-1','愛媛県松山市福角町甲1409番地'))
  self.assertTrue(r.gsi_exact('松山市福音寺町295番地','愛媛県松山市福音寺町295番地'))
 def test_exact_municipality_and_chome(self):
  self.assertEqual(r.city_town_suffix('伊予郡砥部町原町3丁目7-28','砥部町','原町三丁目'),'7-28')
  self.assertIsNone(r.city_town_suffix('松山市三番町3丁目7-28','松山市','三番町二丁目'))
 def test_match_exact_csv_no_partial(self):
  m=r.ABR()
  m.fetch_towns=lambda city:[({'csv_ranges':{'地番':{'start':11,'length':22}}},'高岡町')]
  m.get_range=lambda c,kind,span:[
   ['地番','高岡町'],['prc_num1','prc_num2','prc_num3','lng','lat'],
   ['877','2','', '132.7105','33.8304'],['877','','','132.7100','33.8300']]
  ] if kind=='地番' else []
  yes=m.match('松山市高岡町877-2')
  self.assertEqual(yes['precision'],'street')
  self.assertEqual(yes['evidence'],'exact-city-town-and-all-address-numbers')
  self.assertIsNone(m.match('松山市高岡町877-3'))
  self.assertIsNone(m.match('松山市高岡町877-2-1'))
 def test_ambiguous_rejected(self):
  m=r.ABR()
  m.fetch_towns=lambda city:[({'csv_ranges':{'地番':{'start':11,'length':22}}},'高岡町')]
  m.get_range=lambda c,kind,span:[
    ['地番','高岡町'],['prc_num1','prc_num2','prc_num3','lng','lat'],
    ['877','2','','132.7105','33.8304'],['877','2','','132.8500','33.8304']]
  ]
  self.assertIsNone(m.match('松山市高岡町877-2'))
 def test_precision_increments_and_preserves(self):
  old={'idA':{'address':'松山市高岡町877-2','coord':[132.7,33.8],
       'precision':'district','geocode_title':'愛媛県松山市高岡町877番地'},
       'idB':{'address':'松山市福音寺町295番地','coord':[132.8,33.8],
       'precision':'district','geocode_title':'愛媛県松山市福音寺町295番地'},
       'idC':{'address':'松山市立花3-7-28','coord':[132.8,33.8],
       'precision':'street','geocode_title':'愛媛県松山市立花三丁目７番２８号'}}
  class Matcher:
   def match(self,addr):
    if addr.endswith('877-2'):return {'coord':[132.75,33.85],
      'precision':'street','source':'ABR','evidence':'exact'}
    return None
  fac=[{'id':k,'address':v['address']} for k,v in old.items()]
  revised,stats=r.refine(fac,old,Matcher())
  self.assertEqual(stats['abr_upgrades'],1)
  self.assertEqual(stats['gsi_upgrades'],1)
  self.assertEqual(revised['idC'],old['idC'])
  self.assertEqual(revised['idA']['source'],'ABR')
if __name__=='__main__':unittest.main()
