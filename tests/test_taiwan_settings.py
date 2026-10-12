import copy
import unittest
from unittest.mock import patch
from easyread import chat_models, config, i18n, presets


class TaiwanSettingsTest(unittest.TestCase):
    def test_new_install_only_has_codex_card(self):
        self.assertEqual([m['engine'] for m in chat_models.DEFAULT_MODELS], ['codex'])

    def test_visible_presets_have_no_china_shortcuts_or_price_promises(self):
        with patch.object(i18n, 'lang', return_value='zh-TW'):
            visible = presets.presets()
            self.assertEqual({g for g, _ in presets.preset_groups()}, {'intl', 'local'})
        self.assertFalse(any(p['region'] == 'cn' for p in visible))
        self.assertTrue(all(not p['free'] and not p['models'] and not p['model'] for p in visible))
        self.assertIn('openai', {p['id'] for p in visible})
        self.assertIn('ollama', {p['id'] for p in visible})

    def test_legacy_api_card_edit_preserves_endpoint_model_and_key(self):
        cfg=copy.deepcopy(config.DEFAULTS)
        cfg['chat']={'default':'legacy','models':[{'id':'legacy','engine':'openai','preset':'deepseek','model':'','name':'Saved model'}]}
        cfg['openai'].update(preset='deepseek',base_url='https://api.deepseek.com',keys={'deepseek':'SYNTHETIC'})
        before,_=chat_models.engine_cfg(cfg,'legacy')
        with patch('easyread.detect.detect',return_value={}):
            result=chat_models.listing(cfg)
        cfg['chat']['models']=chat_models.sanitize(result['models'])
        after,_=chat_models.engine_cfg(cfg,'legacy')
        for field in ('base_url','model','api_key','api'):
            self.assertEqual(before['openai'][field],after['openai'][field])
        self.assertNotIn('deepseek',{p['id'] for p in result['presets']})

    def test_custom_api_can_still_be_added(self):
        item={'id':'custom','engine':'openai','name':'My service','base_url':'https://service.example/v1','model':'research-model','api':'chat'}
        cfg=copy.deepcopy(config.DEFAULTS)
        cfg['chat']={'default':'custom','models':chat_models.sanitize([item])}
        active,_=chat_models.engine_cfg(cfg,'custom')
        self.assertEqual(active['openai']['base_url'],item['base_url'])
        self.assertEqual(active['openai']['model'],item['model'])
