import json
import unittest
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
class TestPublishedCoordinates(unittest.TestCase):
 def test_every_licensed_facility_has_a_coordinate_record(self):
  permits=json.loads((BASE/'data/licensed_lodging.json').read_text(encoding='utf-8'))['facilities']
  payload=json.loads((BASE/'data/permit_coordinates.json').read_text(encoding='utf-8'))
  coords=payload['coordinates']
  self.assertEqual(set(x['id'] for x in permits),set(coords))
  s=payload['summary']
  self.assertEqual(s['attempted'],len(permits))
  self.assertEqual(s['street']+s['district']+s['unresolved'],len(permits))
  self.assertEqual(s['street'],sum(v['precision']=='street' for v in coords.values()))
  sources={'GSI address search','Geolonia Japanese Addresses v2 / Digital Agency ABR'}
  for f in permits:
   p=coords[f['id']]
   self.assertEqual(p['address'],f['address'])
   self.assertIn(p['precision'],('street','district','unresolved'))
   point=p.get('coord')
   if point is not None:
    self.assertTrue(132<=point[0]<=134.2 and 32.8<=point[1]<=34.5)
   if p.get('source')=='Geolonia Japanese Addresses v2 / Digital Agency ABR':
    self.assertEqual(p['evidence'],'exact-city-town-and-all-address-numbers')
    self.assertEqual(p['license'],'CC BY 4.0')
    self.assertTrue(p['source_url'].startswith('https://github.com/geolonia/'))
    self.assertIn('matched_address',p)
    self.assertEqual(p['precision'],'street')
    self.assertIn(p['address_level'],('地番','住居表示'))
 def test_refinement_provenance(self):
  payload=json.loads((BASE/'data/permit_coordinates.json').read_text(encoding='utf-8'))
  refinement=payload.get('refinement')
  if refinement:
   self.assertEqual(refinement['after']['street'],payload['summary']['street'])
   self.assertGreaterEqual(payload['summary']['street'],refinement['before']['street'])
   self.assertEqual(refinement['upgraded'],refinement['gsi_upgrades']+refinement['abr_upgrades'])
if __name__=='__main__':unittest.main()
