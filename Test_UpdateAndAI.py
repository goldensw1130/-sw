# -*- coding: utf-8 -*-
"""v2.38 다중 AI 프록시/모델 목록·라우팅/업데이트 작업실의 로컬 단위 테스트. 외부 네트워크·실키 사용 없음."""
import hashlib
import base64
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from urllib.request import Request
from urllib.error import HTTPError
from unittest.mock import patch
import ShortCompassServer as app

class FakeResponse:
    def __init__(self, payload, status=200, url=None):
        self.raw=json.dumps(payload).encode('utf-8')
        self.status=status
        self.headers={}
        self.url=url
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n=-1): return self.raw if n < 0 else self.raw[:n]
    def geturl(self): return self.url or 'https://api.openai.com/v1/responses'


def update_zip(version='2.38', extra=None):
    buf=io.BytesIO()
    items={
        'ShortsCompass.html': f'<title>숏폼 나침반 v{version} 업데이트</title>'.encode('utf-8'),
        'ShortCompassServer.py': f"APP_VERSION = '{version}'\n".encode('utf-8'),
        'Start_ShortCompass.bat': b'@echo off\r\n',
    }
    if extra: items.update(extra)
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for name, data in items.items(): z.writestr(name,data)
    return buf.getvalue()

class VersionAndURLTests(unittest.TestCase):
    def test_version_comparison_pads_missing_components(self):
        self.assertEqual(app._version_tuple('v2.37'),app._version_tuple('2.37.0'))
        self.assertGreater(app._version_tuple('2.100'),app._version_tuple('2.99'))
        self.assertRaises(ValueError,app._version_tuple,'latest')

    def test_allowlist_requires_https_and_github_host(self):
        self.assertTrue(app._https_github_url('https://raw.githubusercontent.com/o/r/main/update_manifest.json'))
        self.assertTrue(app._https_github_url('https://github.com/o/r/releases/download/v2.38/ShortCompass.zip'))
        for url in ('http://github.com/o/r/file','https://evil.example/manifest.json','https://user:pass@github.com/o/r','file:///tmp/x'):
            self.assertFalse(app._https_github_url(url),url)

    def test_redirect_guard_blocks_untrusted_hops_and_ai_redirects(self):
        handler=app._GitHubRedirectGuard()
        req=Request('https://github.com/a/b/releases')
        with self.assertRaises(HTTPError):
            handler.redirect_request(req,io.BytesIO(b''),302,'Found',{},'http://127.0.0.1/private')
        with self.assertRaises(HTTPError):
            handler.redirect_request(req,io.BytesIO(b''),302,'Found',{},'https://evil.example/steal')
        allowed=handler.redirect_request(req,io.BytesIO(b''),302,'Found',{},'https://release-assets.githubusercontent.com/a.zip')
        self.assertTrue(allowed.full_url.startswith('https://release-assets.githubusercontent.com/'))
        with self.assertRaises(HTTPError):
            app._NoRedirectForSecretAPI().redirect_request(Request('https://api.openai.com/v1/responses'),io.BytesIO(b''),302,'Found',{},'https://evil.example/steal')


    def test_old_empty_feed_settings_migrate_to_embedded_url_when_auto_check_enabled(self):
        with tempfile.TemporaryDirectory() as td, patch.object(app, 'UPDATE_SETTINGS_PATH', Path(td) / 'old-settings.json'), patch.object(app, 'DEFAULT_UPDATE_MANIFEST_URL', 'https://github.com/acme/shortcompass/releases/latest/download/update_manifest.json'):
            (Path(td) / 'old-settings.json').write_text(json.dumps({'manifestUrl':'','autoCheck':True,'autoDownload':False,'intervalHours':24}), encoding='utf-8')
            settings = app._read_update_settings()
            self.assertEqual(settings['manifestUrl'], 'https://github.com/acme/shortcompass/releases/latest/download/update_manifest.json')
        with tempfile.TemporaryDirectory() as td, patch.object(app, 'UPDATE_SETTINGS_PATH', Path(td) / 'paused-settings.json'), patch.object(app, 'DEFAULT_UPDATE_MANIFEST_URL', 'https://github.com/acme/shortcompass/releases/latest/download/update_manifest.json'):
            (Path(td) / 'paused-settings.json').write_text(json.dumps({'manifestUrl':'','autoCheck':False,'autoDownload':False,'intervalHours':24}), encoding='utf-8')
            self.assertEqual(app._read_update_settings()['manifestUrl'], '')

    def test_fresh_install_reads_embedded_release_manifest_url(self):
        with tempfile.TemporaryDirectory() as td, patch.object(app, 'UPDATE_SETTINGS_PATH', Path(td) / 'missing-settings.json'), patch.object(app, 'DEFAULT_UPDATE_MANIFEST_URL', 'https://github.com/acme/shortcompass/releases/latest/download/update_manifest.json'):
            settings = app._read_update_settings()
            self.assertEqual(settings['manifestUrl'], 'https://github.com/acme/shortcompass/releases/latest/download/update_manifest.json')
            self.assertTrue(settings['autoCheck'])
            self.assertFalse(settings['autoDownload'])

    def test_update_config_rejects_untrusted_url_and_accepts_trusted(self):
        with tempfile.TemporaryDirectory() as td, patch.object(app,'UPDATE_SETTINGS_PATH',Path(td)/'settings.json'):
            code,bad=app.save_update_settings({'manifestUrl':'https://evil.example/update.json'})
            self.assertEqual(code,400); self.assertEqual(bad['error'],'INVALID_MANIFEST_URL')
            code,good=app.save_update_settings({'manifestUrl':'https://raw.githubusercontent.com/a/b/main/update_manifest.json','autoCheck':True,'autoDownload':True,'intervalHours':6})
            self.assertEqual(code,200); self.assertEqual(good['settings']['intervalHours'],6); self.assertTrue(good['settings']['autoDownload'])
            saved=json.loads((Path(td)/'settings.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['manifestUrl'],'https://raw.githubusercontent.com/a/b/main/update_manifest.json')
            self.assertTrue(saved['autoDownload'])

    def test_zip_checksum_and_version_match(self):
        blob=update_zip()
        digest=hashlib.sha256(blob).hexdigest()
        got,names=app._validate_update_zip_bytes(blob,digest,'2.38')
        self.assertEqual(got,digest); self.assertIn('ShortsCompass.html',names)
        with self.assertRaisesRegex(ValueError,'SHA-256'):
            app._validate_update_zip_bytes(blob,'0'*64,'2.38')
        with self.assertRaisesRegex(ValueError,'manifest 버전'):
            app._validate_update_zip_bytes(blob,digest,'2.39')

    def test_zip_slip_and_unapproved_files_rejected(self):
        traversal=update_zip(extra={'../evil.py':b'bad'})
        with self.assertRaisesRegex(ValueError,'허용하지 않는 패키지 경로'):
            app._validate_update_zip_bytes(traversal,hashlib.sha256(traversal).hexdigest(),'2.38')
        unapproved=update_zip(extra={'README.md':b'not allowed'})
        with self.assertRaisesRegex(ValueError,'허용하지 않는 패키지 경로'):
            app._validate_update_zip_bytes(unapproved,hashlib.sha256(unapproved).hexdigest(),'2.38')

    def test_bad_html_version_rejected(self):
        blob=update_zip()
        # The server file version is 2.38 but actual HTML title is intentionally inconsistent.
        buf=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(blob)) as src, zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as dst:
            for item in src.infolist():
                data=src.read(item.filename)
                if item.filename=='ShortsCompass.html': data='<title>숏폼 나침반 v2.37 old</title>'.encode('utf-8')
                dst.writestr(item.filename,data)
        changed=buf.getvalue()
        with self.assertRaisesRegex(ValueError,'HTML 화면의 버전'):
            app._validate_update_zip_bytes(changed,hashlib.sha256(changed).hexdigest(),'2.38')

    def test_update_settings_auto_download_is_opt_in_by_default(self):
        with tempfile.TemporaryDirectory() as td, patch.object(app,'UPDATE_SETTINGS_PATH',Path(td)/'settings.json'):
            settings=app._read_update_settings()
            self.assertFalse(settings['autoDownload'])
            code,result=app.save_update_settings({'manifestUrl':'','autoCheck':True,'intervalHours':24})
            self.assertEqual(code,200)
            self.assertFalse(result['settings']['autoDownload'])

    def test_update_check_unconfigured_is_honest(self):
        with tempfile.TemporaryDirectory() as td, patch.object(app,'DEFAULT_UPDATE_MANIFEST_URL',''), patch.object(app,'UPDATE_SETTINGS_PATH',Path(td)/'settings.json'), patch.object(app,'UPDATE_STATE_PATH',Path(td)/'state.json'), patch.object(app,'UPDATE_STAGE_PATH',Path(td)/'updates'/'stage.zip'), patch.object(app,'_fetch_https_json') as fetch:
            result=app.check_for_update(force=True)
            self.assertTrue(result['ok']); self.assertFalse(result['configured']); self.assertFalse(result['updateAvailable'])
            fetch.assert_not_called()

    def test_update_check_uses_manifest_and_numeric_version(self):
        manifest={'schemaVersion':1,'version':'2.47','minimumVersion':'2.38','downloadUrl':'https://github.com/a/b/releases/download/v2.47/app.zip','sha256':'a'*64,'releaseNotes':'test'}
        with tempfile.TemporaryDirectory() as td, patch.object(app,'UPDATE_SETTINGS_PATH',Path(td)/'settings.json'), patch.object(app,'UPDATE_STATE_PATH',Path(td)/'state.json'), patch.object(app,'UPDATE_STAGE_PATH',Path(td)/'updates'/'stage.zip'), patch.object(app,'_fetch_https_json',return_value=manifest) as fetch:
            app._write_json_file(Path(td)/'settings.json',{'manifestUrl':'https://raw.githubusercontent.com/a/b/main/update_manifest.json','autoCheck':True,'intervalHours':24})
            result=app.check_for_update(force=True)
            self.assertTrue(result['ok']); self.assertTrue(result['updateAvailable']); self.assertEqual(result['availableVersion'],'2.47')
            fetch.assert_called_once()

class AIWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.old={k:app.SESSION_AI_KEYS.get(k,'') for k in app.SESSION_AI_KEYS}
        self.env_patch=patch.dict(os.environ,{'OPENAI_API_KEY':'','GEMINI_API_KEY':'','ANTHROPIC_API_KEY':''})
        self.env_patch.start()
        for k in app.SESSION_AI_KEYS: app.SESSION_AI_KEYS[k]=''
    def tearDown(self):
        for k,v in self.old.items(): app.SESSION_AI_KEYS[k]=v
        self.env_patch.stop()

    def test_status_never_returns_actual_keys(self):
        app.SESSION_AI_KEYS['openai']='mock-secret-for-test'
        status=app.ai_status_view()
        serialized=json.dumps(status)
        self.assertNotIn('mock-secret-for-test',serialized)
        self.assertTrue(next(p for p in status['providers'] if p['id']=='openai')['configured'])

    def test_session_key_not_written_to_disk(self):
        with tempfile.TemporaryDirectory() as td, patch.object(app,'AI_MODELS_PATH',Path(td)/'models.json'):
            code,result=app.configure_ai_session({'provider':'openai','key':'mock-secret-for-test','model':'gpt-6.1-sol'})
            self.assertEqual(code,200)
            self.assertNotIn('mock-secret-for-test',json.dumps(result))
            self.assertNotIn('mock-secret-for-test',(Path(td)/'models.json').read_text(encoding='utf-8'))
            self.assertEqual(app.SESSION_AI_KEYS['openai'],'mock-secret-for-test')

    def test_invalid_model_does_not_change_session_key(self):
        app.SESSION_AI_KEYS['openai']='old-session-key'
        code,result=app.configure_ai_session({'provider':'openai','key':'new-session-key','model':'bad model !'})
        self.assertEqual(code,400); self.assertEqual(result['error'],'INVALID_MODEL')
        self.assertEqual(app.SESSION_AI_KEYS['openai'],'old-session-key')

    def test_missing_key_empty_prompt_and_invalid_task_stop_before_network(self):
        with patch.object(app,'_open_provider_url') as net:
            code,missing=app.generate_with_provider({'provider':'openai','task':'script','prompt':'hello','model':'gpt-6.1-sol'})
            self.assertEqual(code,400); self.assertEqual(missing['error'],'MISSING_API_KEY')
            app.SESSION_AI_KEYS['openai']='mock-key'
            code,empty=app.generate_with_provider({'provider':'openai','task':'script','prompt':'  '})
            self.assertEqual(code,400); self.assertEqual(empty['error'],'EMPTY_PROMPT')
            code,task=app.generate_with_provider({'provider':'openai','task':'destroy','prompt':'hello'})
            self.assertEqual(code,400); self.assertEqual(task['error'],'INVALID_TASK')
            net.assert_not_called()

    def test_mocked_generation_for_all_three_providers(self):
        provider_responses={
            'openai':{'output_text':'모의 OpenAI 응답'},
            'gemini':{'candidates':[{'content':{'parts':[{'text':'모의 Gemini 응답'}]}}]},
            'anthropic':{'content':[{'type':'text','text':'모의 Claude 응답'}]},
        }
        with tempfile.TemporaryDirectory() as td, patch.object(app,'AI_MODELS_PATH',Path(td)/'models.json'), patch('ShortCompassServer.time.sleep'):
            for provider,payload in provider_responses.items():
                app.SESSION_AI_KEYS[provider]='mock-key-'+provider
                with patch.object(app,'_open_provider_url',return_value=FakeResponse(payload)) as network:
                    code,result=app.generate_with_provider({'provider':provider,'task':'script','prompt':'테스트 프롬프트','model':app.AI_DEFAULT_MODELS[provider]})
                self.assertEqual(code,200,(provider,result))
                self.assertIn('모의',result['text'])
                req=network.call_args.args[0]
                self.assertTrue(req.full_url.startswith('https://'))
                self.assertEqual(network.call_args.kwargs.get('provider'),provider)
                self.assertNotIn('mock-key-'+provider,json.dumps(result))

    def test_model_list_without_key_does_not_call_network(self):
        for provider in ('openai','gemini','anthropic'):
            with patch.object(app,'_open_provider_url') as net:
                code,result=app.list_provider_models({'provider':provider})
            self.assertEqual(code,400)
            self.assertEqual(result['error'],'MISSING_API_KEY')
            net.assert_not_called()

    def test_model_catalog_normalizes_provider_formats_and_never_returns_keys(self):
        fixtures={
            'openai':{'data':[{'id':'gpt-6-astra','display_name':'Astra'},{'id':'gpt-6.1-sol'}]},
            'gemini':{'models':[{'name':'models/gemini-4-argon','displayName':'Argon','supportedGenerationMethods':['generateContent']},{'name':'models/text-embedding-only','supportedGenerationMethods':['embedContent']}]},
            'anthropic':{'data':[{'id':'claude-opus-5','display_name':'Opus'}]},
        }
        with tempfile.TemporaryDirectory() as td, patch.object(app,'AI_MODELS_PATH',Path(td)/'models.json'):
            for provider in ('openai','gemini','anthropic'):
                secret='test-secret-'+provider
                app.SESSION_AI_KEYS[provider]=secret
                with patch.object(app,'_open_provider_url',return_value=FakeResponse(fixtures[provider])) as network:
                    code,result=app.list_provider_models({'provider':provider})
                self.assertEqual(code,200,(provider,result))
                self.assertGreaterEqual(result['count'],1)
                self.assertNotIn(secret,json.dumps(result))
                req=network.call_args.args[0]
                self.assertTrue(req.full_url.startswith(app.AI_MODEL_LIST_ENDPOINTS[provider].split('?')[0]))
                self.assertEqual(network.call_args.kwargs.get('provider'),provider)
                auth_headers=' '.join(str(v) for v in req.header_items())
                self.assertIn(secret,auth_headers)
                if provider=='gemini':
                    self.assertEqual([x['id'] for x in result['models']],['gemini-4-argon'])

    def test_connection_test_uses_small_output_budget_and_redacts_key(self):
        app.SESSION_AI_KEYS['openai']='private-test-key'
        with tempfile.TemporaryDirectory() as td, patch.object(app,'AI_MODELS_PATH',Path(td)/'models.json'), patch.object(app,'_open_provider_url',return_value=FakeResponse({'output_text':'READY'})) as network, patch('ShortCompassServer.time.sleep'):
            code,result=app.test_provider_connection({'provider':'openai','model':'gpt-6-astra'})
        self.assertEqual(code,200,result)
        req=network.call_args.args[0]
        body=json.loads(req.data.decode('utf-8'))
        self.assertEqual(body['max_output_tokens'],24)
        self.assertIn('READY',str(body))
        self.assertNotIn('private-test-key',json.dumps(result))

    def test_auto_router_uses_task_priority_and_fallback_is_opt_in(self):
        app.SESSION_AI_KEYS['anthropic']='a-test-key'
        app.SESSION_AI_KEYS['openai']='o-test-key'
        with tempfile.TemporaryDirectory() as td, patch.object(app,'AI_MODELS_PATH',Path(td)/'models.json'):
            with patch.object(app,'generate_with_provider',return_value=(200,{'ok':True,'text':'works','provider':'anthropic','model':'claude-opus-5','elapsedMs':3,'note':'test'})) as gen:
                code,result=app.auto_generate_with_router({'task':'script','prompt':'hi','allowFallback':False})
                self.assertEqual(code,200,result)
                self.assertEqual(gen.call_count,1)
                self.assertEqual(gen.call_args.args[0]['provider'],'anthropic')
            with patch.object(app,'generate_with_provider',side_effect=[(502,{'ok':False,'error':'mock'}),(200,{'ok':True,'text':'works','provider':'openai','model':'gpt-6-astra','elapsedMs':3,'note':'test'})]) as gen:
                code,result=app.auto_generate_with_router({'task':'script','prompt':'hi','allowFallback':True})
                self.assertEqual(code,200,result)
                self.assertEqual(gen.call_count,2)
                self.assertTrue(result['attempts'][0]['ok'] is False)
                self.assertIn('실패',result['note'])

    def test_images_require_matching_real_file_signature_and_limit_count(self):
        png=b'\x89PNG\r\n\x1a\nsample-png-payload'
        valid='data:image/png;base64,'+base64.b64encode(png).decode('ascii')
        normalized=app._normalize_ai_images([{'time':2.5,'dataUrl':valid}])
        self.assertEqual(normalized[0]['mimeType'],'image/png')
        self.assertEqual(normalized[0]['time'],2.5)
        spoof='data:image/png;base64,'+base64.b64encode(b'not really png').decode('ascii')
        with self.assertRaisesRegex(ValueError,'파일 형식'):
            app._normalize_ai_images([{'dataUrl':spoof}])
        with self.assertRaisesRegex(ValueError,'최대 8장'):
            app._normalize_ai_images([{'dataUrl':valid} for _ in range(9)])

    def test_openai_multimodal_payload_is_built_through_local_proxy_logic(self):
        app.SESSION_AI_KEYS['openai']='private-frame-key'
        png=b'\x89PNG\r\n\x1a\nsample-png-payload'
        data_url='data:image/png;base64,'+base64.b64encode(png).decode('ascii')
        with tempfile.TemporaryDirectory() as td, patch.object(app,'AI_MODELS_PATH',Path(td)/'models.json'), patch.object(app,'_open_provider_url',return_value=FakeResponse({'output_text':'frame reviewed'})) as network, patch('ShortCompassServer.time.sleep'):
            code,result=app.generate_with_provider({'provider':'openai','task':'script','prompt':'summarize frame','images':[{'time':7,'dataUrl':data_url}]})
        self.assertEqual(code,200,result)
        body=json.loads(network.call_args.args[0].data.decode('utf-8'))
        kinds=[part.get('type') for part in body['input'][0]['content']]
        self.assertIn('input_image',kinds)
        self.assertNotIn('private-frame-key',json.dumps(result))

    def test_old_frontend_ai_actions_use_local_proxy(self):
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn("localJson('/api/ai/generate'",source)
        self.assertIn("localJson('/api/ai/models'",source)
        self.assertIn("const route=auto?'/api/ai/auto-generate'",source)
        self.assertNotIn('fetch(\'https://api.openai.com/v1/responses',source)
        self.assertNotIn('fetch(\'https://generativelanguage.googleapis.com/v1beta/models/',source)
        self.assertIn("const connection=(aiState.providers||[]).find(p=>p.id===provider)",source)

    def test_policy_precheck_flags_misleading_monetization(self):
        result=app.policy_precheck({'text':'이 영상으로 무조건 수익 보장, 기존 영상을 그대로 재업로드하세요.'})
        self.assertTrue(result['ok']); self.assertEqual(result['status'],'REVIEW_REQUIRED')
        self.assertGreaterEqual(result['matchedRules'],2)

    def test_policy_precheck_disclaims_that_no_match_is_not_a_guarantee(self):
        result=app.policy_precheck({'text':'오늘은 제가 직접 촬영한 종이접기 방법을 소개합니다.'})
        self.assertTrue(result['ok']); self.assertEqual(result['status'],'NO_RULE_MATCH')
        self.assertIn('보증이 아닙니다',result['note'])


class FullDiagnosticsTests(unittest.TestCase):
    def test_report_has_version_state_and_never_includes_api_key(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); root=base/'app'; data=base/'user-data'
            root.mkdir(); data.mkdir()
            (root/'ShortCompassServer.py').write_text("APP_VERSION = '2.46'\n",encoding='utf-8')
            (root/'ShortsCompass.html').write_text("<title>숏폼 나침반 v2.46 테스트</title><div class='footer'>숏폼 나침반 v2.46</div>backupMeta:{app:'ShortCompass',version:'2.46',exportedAt:new Date().toISOString()}",encoding='utf-8')
            (root/'Start_ShortCompass.bat').write_text('@echo off',encoding='utf-8')
            for name in ['Prepare_Release.py','release_workflow_template.yml','RELEASE_PUBLISHING_GUIDE_KO.md','Test_ReleaseTools.py']:
                (root/name).write_text('test',encoding='utf-8')
            settings=data/'update_settings.json'
            settings.write_text(json.dumps({'manifestUrl':'','autoCheck':True,'autoDownload':False,'intervalHours':24}),encoding='utf-8')
            paths={
                'ROOT':root, 'USER_DATA_ROOT':data, 'UPDATE_SETTINGS_PATH':settings,
                'UPDATE_STATE_PATH':data/'update_state.json','UPDATE_STAGE_PATH':data/'updates'/'verified-update.zip',
                'AI_MODELS_PATH':data/'ai_models.json', 'DEFAULT_UPDATE_MANIFEST_URL':''
            }
            old={k: getattr(app,k) for k in paths}
            old_keys=dict(app.SESSION_AI_KEYS)
            try:
                for k,v in paths.items(): setattr(app,k,v)
                for k in app.SESSION_AI_KEYS: app.SESSION_AI_KEYS[k]=''
                app.SESSION_AI_KEYS['openai']='do-not-leak-this-secret'
                with patch.dict(os.environ, {'OPENAI_API_KEY':'','GEMINI_API_KEY':'','ANTHROPIC_API_KEY':''}):
                    result=app.run_full_diagnostics()
                serialized=json.dumps(result,ensure_ascii=False)
                self.assertNotIn('do-not-leak-this-secret',serialized)
                self.assertIn('version-alignment',[x['code'] for x in result['checks']])
                version_check=next(x for x in result['checks'] if x['code']=='version-alignment')
                self.assertEqual(version_check['status'],'PASS')
                ai_check=next(x for x in result['checks'] if x['code']=='ai-providers')
                self.assertTrue(ai_check['detail'][0]['configured'])
                self.assertNotIn('do-not-leak-this-secret',json.dumps(ai_check['detail']))
                update_check=next(x for x in result['checks'] if x['code']=='update-feed')
                self.assertEqual(update_check['status'],'WARN')
            finally:
                for k,v in old.items(): setattr(app,k,v)
                app.SESSION_AI_KEYS.update(old_keys)

    def test_report_detects_html_version_mismatch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base=Path(td); root=base/'app'; data=base/'data'; root.mkdir(); data.mkdir()
            (root/'ShortCompassServer.py').write_text("APP_VERSION = '2.39'\n",encoding='utf-8')
            (root/'ShortsCompass.html').write_text("<title>숏폼 나침반 v2.38 테스트</title><div class='footer'>숏폼 나침반 v2.38</div>backupMeta:{app:'ShortCompass',version:'2.38',exportedAt:new Date().toISOString()}",encoding='utf-8')
            (root/'Start_ShortCompass.bat').write_text('@echo off',encoding='utf-8')
            paths={'ROOT':root,'USER_DATA_ROOT':data,'UPDATE_SETTINGS_PATH':data/'u.json','UPDATE_STATE_PATH':data/'s.json','UPDATE_STAGE_PATH':data/'updates'/'stage.zip','AI_MODELS_PATH':data/'models.json'}
            old={k:getattr(app,k) for k in paths}; old_keys=dict(app.SESSION_AI_KEYS)
            try:
                for k,v in paths.items(): setattr(app,k,v)
                for k in app.SESSION_AI_KEYS: app.SESSION_AI_KEYS[k]=''
                with patch.dict(os.environ, {'OPENAI_API_KEY':'','GEMINI_API_KEY':'','ANTHROPIC_API_KEY':''}): result=app.run_full_diagnostics()
                row=next(x for x in result['checks'] if x['code']=='version-alignment')
                self.assertEqual(row['status'],'FAIL')
                self.assertFalse(result['ok'])
            finally:
                for k,v in old.items(): setattr(app,k,v)
                app.SESSION_AI_KEYS.update(old_keys)

if __name__=='__main__': unittest.main(verbosity=2)
