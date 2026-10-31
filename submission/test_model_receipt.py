"""No provider call and no mock counted as Meta authenticity."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from model_receipt import load_receipt

class ModelReceiptPresentationTest(unittest.TestCase):
    def test_no_receipt_means_not_recorded(self):
        with patch.dict(os.environ, {}, clear=True):
            result = load_receipt()
        self.assertEqual(result['status'],'NOT_RECORDED')
        self.assertFalse(result['is_authenticated_by_app'])

    def test_invalid_or_forged_receipt_not_displayed_as_meta(self):
        with TemporaryDirectory() as d:
            f=Path(d)/'fake.json'
            f.write_text(json.dumps({'kind':'repair-bench.a11y.muse-trial.v1','model':'gemma-4','real_model_inference':True}))
            with patch.dict(os.environ, {'RB_META_TRIAL_RECEIPT':str(f)}):
                result=load_receipt()
        self.assertEqual(result['status'],'INVALID_RECEIPT')
        self.assertFalse(result['is_authenticated_by_app'])

    def test_well_formed_operator_receipt_is_still_unverified(self):
        with TemporaryDirectory() as d:
            f=Path(d)/'trial.json'
            f.write_text(json.dumps({
                'kind':'repair-bench.a11y.muse-trial.v1','provider':'Meta Model API','model':'muse-spark-1.3',
                'request_sha256':'a'*64, 'candidate':{'schema':'repair-bench.a11y-proposal.v1','repair':'native_button'},
                'verification':{'real_model_inference':True,'repair_type':'native_button','acceptance':'ACCEPTED'},
                'provider_identity':{'raw_response_sha256':'b'*64,'response_id':'SYNTHETIC_TEST'},
            }))
            with patch.dict(os.environ, {'RB_META_TRIAL_RECEIPT':str(f)}):
                result=load_receipt()
        self.assertEqual(result['status'],'OPERATOR_RECEIPT_PRESENT_UNVERIFIED')
        self.assertFalse(result['is_authenticated_by_app'])
        self.assertTrue(result['response_id_present'])

if __name__ == '__main__':unittest.main()

class DialogReceiptTests(unittest.TestCase):
    def test_operator_supplied_dialog_receipt_remains_unverified(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        with TemporaryDirectory() as directory:
            path=Path(directory)/'operator.json'
            path.write_text(json.dumps({'kind':'repair-bench.dialog.muse-trial.v1','task':'dialog',
               'provider':'Meta Model API','model':'muse-spark-1.3','request_sha256':'a'*64,
               'candidate':{'schema':'repair-bench.dialog-proposal.v1','repair':'managed_dialog'},
               'verification':{'real_model_inference':True,'repair_type':'managed_dialog','acceptance':'ACCEPTED'},
               'provider_identity':{'raw_response_sha256':'b'*64}}))
            with patch.dict(os.environ,{'RB_META_TRIAL_RECEIPT':str(path)}):result=load_receipt()
        self.assertEqual(result['status'],'OPERATOR_RECEIPT_PRESENT_UNVERIFIED')
        self.assertEqual(result['task'],'dialog')
        self.assertFalse(result['is_authenticated_by_app'])
