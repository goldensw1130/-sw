# -*- coding: utf-8 -*-
"""숏폼 나침반 로컬 회귀 테스트. 실제 외부 API에 연결하지 않고 모의 응답을 사용합니다."""
import json
import unittest
from unittest.mock import patch
import ShortCompassServer as app

class FakeResponse:
    def __init__(self, payload, status=200):
        self.raw=json.dumps(payload).encode('utf-8')
        self.status=status
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n=-1): return self.raw if n < 0 else self.raw[:n]

class ResearchApiTests(unittest.TestCase):
    def payload(self, **overrides):
        from datetime import datetime, timezone, timedelta
        today=datetime.now(timezone.utc).date()
        data={'client_key':'test-key','client_secret':'test-secret','query':'cooking','region':'KR',
              'start_date':(today-timedelta(days=6)).isoformat(),'end_date':today.isoformat()}
        data.update(overrides)
        return data

    def test_missing_credentials_does_not_network(self):
        with patch.object(app, 'urlopen') as net:
            status, data=app.run_tiktok_research_search(self.payload(client_secret=''))
        self.assertEqual(status,400)
        self.assertEqual(data['error'],'MISSING_CREDENTIALS')
        net.assert_not_called()

    def test_rejects_overlong_date_range(self):
        from datetime import datetime, timezone, timedelta
        today=datetime.now(timezone.utc).date()
        with patch.object(app, 'urlopen') as net:
            status, data=app.run_tiktok_research_search(self.payload(start_date=(today-timedelta(days=31)).isoformat()))
        self.assertEqual(status,400)
        self.assertEqual(data['error'],'DATE_RANGE_TOO_LONG')
        net.assert_not_called()

    def test_rejects_invalid_max_results_without_network(self):
        with patch.object(app, 'urlopen') as net:
            status, data=app.run_tiktok_research_search(self.payload(max_results=150))
        self.assertEqual(status,400)
        self.assertEqual(data['error'],'INVALID_MAX_RESULTS')
        net.assert_not_called()

    def test_fetches_multiple_pages_and_deduplicates(self):
        from datetime import datetime, timezone, timedelta
        today=datetime.now(timezone.utc).date()
        token={'access_token':'test-token','expires_in':7200,'token_type':'Bearer'}
        first={'data':{'videos':[
            {'id':'100','username':'creator_a','video_description':'low','view_count':12,'like_count':1,'comment_count':0,'share_count':0,'create_time':1700000000,'region_code':'KR'}], 'has_more':True,'cursor':100},'error':{'code':'ok'}}
        second={'data':{'videos':[
            {'id':'100','username':'creator_a','video_description':'duplicate','view_count':12,'create_time':1700000000,'region_code':'KR'},
            {'id':'200','username':'creator_b','video_description':'high','view_count':980,'create_time':1700001000,'region_code':'KR'}], 'has_more':False,'cursor':200},'error':{'code':'ok'}}
        with patch.object(app, 'urlopen', side_effect=[FakeResponse(token),FakeResponse(first),FakeResponse(second)]), patch.object(app.time,'sleep'):
            status, data=app.run_tiktok_research_search(self.payload(max_results=200,start_date=(today-timedelta(days=6)).isoformat(),end_date=today.isoformat()))
        self.assertEqual(status,200)
        self.assertEqual(data['pagesFetched'],2)
        self.assertEqual(data['count'],2)
        self.assertEqual([x['views'] for x in data['results']],[980,12])

    def test_official_results_sorted_by_views(self):
        from datetime import datetime, timezone, timedelta
        today=datetime.now(timezone.utc).date()
        token={'access_token':'test-token','expires_in':7200,'token_type':'Bearer'}
        videos={'data':{'videos':[
            {'id':'100','username':'creator_a','video_description':'low','view_count':12,'like_count':1,'comment_count':0,'share_count':0,'create_time':1700000000,'region_code':'KR'},
            {'id':'200','username':'creator_b','video_description':'high','view_count':980,'like_count':20,'comment_count':4,'share_count':2,'create_time':1700001000,'region_code':'KR'}], 'has_more':False},
            'error':{'code':'ok','message':''}}
        with patch.object(app, 'urlopen', side_effect=[FakeResponse(token),FakeResponse(videos)]):
            payload={'client_key':'test-key','client_secret':'test-secret','query':'cooking','region':'KR','start_date':(today-timedelta(days=6)).isoformat(),'end_date':today.isoformat()}
            status, data=app.run_tiktok_research_search(payload)
        self.assertEqual(status,200)
        self.assertTrue(data['ok'])
        self.assertEqual([x['views'] for x in data['results']],[980,12])
        self.assertIn('/@creator_b/video/200',data['results'][0]['url'])


class SmartSearchRegressionTests(unittest.TestCase):
    def test_numeric_metric_handles_string_counts_and_missing_values(self):
        self.assertEqual(app._numeric_metric('1,234'), 1234.0)
        self.assertEqual(app._numeric_metric(0), 0.0)
        self.assertEqual(app._numeric_metric(None), -1)
        self.assertEqual(app._numeric_metric('not-a-number'), -1)

    def test_tiktok_url_validation_rejects_non_video_pages(self):
        self.assertTrue(app.is_tiktok_video('https://www.tiktok.com/@creator/video/123456'))
        self.assertTrue(app.is_tiktok_video('https://vm.tiktok.com/abc123/'))
        self.assertFalse(app.is_tiktok_video('https://www.tiktok.com/@creator'))
        self.assertFalse(app.is_tiktok_video('https://example.com/video/123456'))

    def test_query_is_normalized_before_search_cache_lookup(self):
        original_cache = dict(app.SEARCH_CACHE)
        try:
            app.SEARCH_CACHE.clear()
            fake={'ok':True,'error':None,'message':'cached test','results':[],'source':'test','providers':[]}
            app._cache_search_result('example query', fake)
            # A cache hit should avoid reaching external providers.
            with patch.object(app, '_fetch_search_provider', side_effect=AssertionError('unexpected network call')):
                result=app.search_public_index('  Example   Query  ')
            self.assertTrue(result.get('cached'))
            self.assertEqual(result['results'], [])
        finally:
            app.SEARCH_CACHE.clear(); app.SEARCH_CACHE.update(original_cache)


    def test_tiktok_canonical_url_removes_tracking_query_and_fragment(self):
        self.assertEqual(app.canonical_tiktok_url('https://WWW.TikTok.com/@creator/video/123/?_t=abc&lang=ko#comments'), 'https://www.tiktok.com/@creator/video/123')

    def test_search_title_normalization_is_stable(self):
        self.assertEqual(app.normalize_search_title('  My Video | TikTok '), app.normalize_search_title('my video'))

    def test_provider_results_deduplicate_tracking_variants(self):
        html="""<html><a class="result__a" href="https://www.tiktok.com/@abc/video/123?lang=en">Video A</a><a class="result__a" href="https://www.tiktok.com/@abc/video/123?lang=ko">Video A | TikTok</a></html>"""
        with patch.object(app, 'urlopen', return_value=FakeResponse({})) as net:
            # The mock response object above returns JSON, so replace with a small HTML response.
            class HtmlResponse(FakeResponse):
                def __init__(self, raw): self.raw=raw.encode(); self.status=200
            with patch.object(app, 'urlopen', return_value=HtmlResponse(html)):
                result=app._fetch_search_provider('duckduckgo','test')
        self.assertEqual(len(result['results']),1)
        self.assertEqual(result['results'][0]['url'],'https://www.tiktok.com/@abc/video/123')


class CategorySearchUiRegressionTests(unittest.TestCase):
    def test_all_eight_categories_are_available_and_select_all_controls_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for category in ('science','life','products','psychology','money','food','technology','mystery'):
            self.assertIn('class="niche-category" value="'+category+'"', source)
        self.assertIn('id="selectAllNicheCategories"', source)
        self.assertIn('id="clearNicheCategories"', source)
        self.assertIn('function updateNicheSelectionCount()', source)

    def test_manual_query_does_not_replace_selected_categories(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        start=source.index('function openSelectedNicheTikTok()')
        end=source.index('let publicIndexAbort', start)
        fn=source[start:end]
        self.assertIn('const rows=ids.map', fn)
        self.assertIn("rows.unshift({id:'custom',name:'직접 입력 검색어',query:manual})", fn)
        self.assertNotIn('const rows=manual?', fn)


class SampleRankingUiRegressionTests(unittest.TestCase):
    def test_sample_sort_options_and_metric_helpers_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for value in ('recent','views','velocity','engagement','score'):
            self.assertIn('<option value="'+value+'"', source)
        self.assertIn('function ttSampleMetrics(x)', source)
        self.assertIn('function ttPercentileScores(samples,key)', source)
        self.assertIn('function ttSampleScores(samples)', source)
        self.assertIn("document.getElementById('ttSampleSort')?.addEventListener('change',renderTikTokSamples)", source)

    def test_csv_includes_relative_sample_score_and_caveat(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('표본 내 상대 성과 점수', source)
        self.assertIn('전체 TikTok 영상의 순위나 미래 조회수를 예측하지 않습니다', source)
        self.assertIn('상대 성과 점수 높은 순', source)


class BackupReliabilityTests(unittest.TestCase):
    def test_backup_import_has_size_limit_and_validation_helpers(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('function normalizeImportedBackup(x)', source)
        self.assertIn('f.size>25*1024*1024', source)
        self.assertIn('기존 데이터는 변경하지 않았습니다', source)

    def test_backup_import_checks_tiktok_sample_metrics_and_deduplicates(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('TikTok 표본이 10,000개를 초과합니다.', source)
        self.assertIn('const seen=new Set(),deduped=[]', source)
        self.assertIn('const duplicate=state.tiktokSamples.some', source)
        self.assertIn('중복 표본', source)

    def test_backup_export_includes_version_and_timestamp_metadata(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn("backupMeta:{app:'ShortCompass',version:'2.46',exportedAt:new Date().toISOString()}", source)
        self.assertIn("'version':APP_VERSION", (Path(__file__).resolve().parent/'ShortCompassServer.py').read_text(encoding='utf-8'))


class OutlierResearchRegressionTests(unittest.TestCase):
    def test_manual_sample_ui_has_channel_baseline_and_outlier_sort(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('id="ttBaselineViews"', source)
        self.assertIn('<option value="outlier">채널 평소 대비 초과 성과순</option>', source)
        self.assertIn('outlierRatio', source)
        self.assertIn('채널 평소 조회수 중앙값', source)

    def test_outlier_ratio_is_computed_only_when_baseline_exists(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('Number.isFinite(baseline)&&baseline>0&&Number.isFinite(views)?views/baseline:null', source)
        self.assertIn("mode==='outlier'?mx.outlierRatio", source)

    def test_baseline_views_is_exported_and_validated(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn("'채널 평소 조회수 중앙값','채널 평소 대비 초과 성과 배수'", source)
        self.assertIn("['likes','comments','shares','followers','baselineViews']", source)



class ViewTrackingRegressionTests(unittest.TestCase):
    def test_sample_refresh_history_and_date_validation_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('function refreshTikTokSample(id)', source)
        self.assertIn('x.history.sort((a,b)=>a.date.localeCompare(b.date))', source)
        self.assertIn('조회수 갱신', source)

    def test_history_summary_computes_delta_only_from_two_snapshots(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('function ttHistorySummary(x)', source)
        self.assertIn('Number(last.views)-Number(first.views)', source)
        self.assertIn('서로 다른 날짜의 기록 2개', source)

    def test_history_is_exported_and_imported_with_validation(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn("Array.isArray(v.history)?v.history.filter", source)
        self.assertIn('조회수 기록 횟수','조회수 기록 횟수')
        self.assertIn('최근 두 기록 증가량', source)


class SearchQualityUiRegressionTests(unittest.TestCase):
    def test_search_quality_history_and_duplicate_normalization_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('function normalizeSearchTitle(title)', source)
        self.assertIn('function recordSearchQuality(query,data,elapsedMs,stage)', source)
        self.assertIn('function renderSearchQualitySummary()', source)
        self.assertIn('searchQualityHistory', source)




class MonetizationLabRegressionTests(unittest.TestCase):
    def test_monetization_lab_ui_and_metrics_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['data-tab="money"','id="money"','function addMonetizationExperiment()', 'function calculateMonetizationGoal()', 'function renderMonetization()', 'function exportMonetizationCsv()', 'monetizationExperiments','monetizationSprint']:
            self.assertIn(marker, source)
    def test_goal_calculator_disclaims_guaranteed_revenue(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('실제 예측이나 수익 보장이 아닙니다.', source)
        self.assertIn('실제 확인한 금액만 입력하세요.', source)



class ProvenanceAndLearningRegressionTests(unittest.TestCase):
    def test_public_index_returns_collection_and_served_timestamps(self):
        original_cache = dict(app.SEARCH_CACHE)
        try:
            app.SEARCH_CACHE.clear()
            good = {'provider':'duckduckgo','error':None,'message':'','results':[{'title':'Video','url':'https://www.tiktok.com/@abc/video/123','source':'DuckDuckGo 공개 웹 색인','metrics':None}],'duplicateCount':0}
            with patch.object(app, '_fetch_search_provider', return_value=good):
                result = app.search_public_index('metadata test')
            self.assertTrue(result['ok'])
            self.assertEqual(result['sourceType'], 'public-web-index')
            self.assertRegex(result['collectedAt'], r'^\d{4}-\d\d-\d\dT')
            cached = app.search_public_index('metadata test')
            self.assertTrue(cached['cached'])
            self.assertEqual(cached['collectedAt'], result['collectedAt'])
            self.assertTrue(cached['servedAt'])
        finally:
            app.SEARCH_CACHE.clear(); app.SEARCH_CACHE.update(original_cache)

    def test_research_success_payload_includes_source_scope_and_timestamp(self):
        from datetime import datetime, timezone, timedelta
        today=datetime.now(timezone.utc).date()
        token={'access_token':'test-token','expires_in':7200,'token_type':'Bearer'}
        videos={'data':{'videos':[{'id':'123','username':'creator','video_description':'test','view_count':20,'like_count':2,'comment_count':1,'share_count':0,'create_time':1700000000,'region_code':'KR'}], 'has_more':False},'error':{'code':'ok','message':''}}
        with patch.object(app, 'urlopen', side_effect=[FakeResponse(token),FakeResponse(videos)]):
            payload={'client_key':'test-key','client_secret':'test-secret','query':'cooking','region':'KR','start_date':(today-timedelta(days=6)).isoformat(),'end_date':today.isoformat()}
            status, data=app.run_tiktok_research_search(payload)
        self.assertEqual(status,200)
        self.assertEqual(data['sourceType'],'official-api')
        self.assertRegex(data['collectedAt'],r'^\d{4}-\d\d-\d\dT')
        self.assertEqual(data['scope']['region'],'KR')
        self.assertEqual(data['scope']['requestedMax'],100)

    def test_client_source_provenance_and_adaptive_rank_gates_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['function opportunityComparableStats(o)', 'function opportunityEmpiricalRanking()', '같은 플랫폼·수익 경로', '실증 반영 점수', 'sourceMeta:x.provenance', 'data.collectedAt', 'sourceMeta:v.sourceMeta', '출처 제공자','backupMeta:{app:\'ShortCompass\',version:\'2.46\'']:
            self.assertIn(marker,source)

    def test_research_api_and_health_version_in_server(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortCompassServer.py').read_text(encoding='utf-8')
        for marker in ["'sourceType':'official-api'", "'collectedAt':collected_at", "'scope':{'region':region", "'version':APP_VERSION"]:
            self.assertIn(marker,source)

    def test_unknown_monetization_metrics_are_not_treated_as_zero(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn("const sumKnown=k=>rows.reduce((n,x)=>n+(x.reported&&x.reported[k]===true?(Number(x[k])||0):0),0)", source)
        self.assertIn("x.reported?.views===true&&x.reported?.clicks===true", source)
        self.assertIn("빈칸은 0으로 계산해 순위를 왜곡하지 않습니다.", source)
        self.assertIn("조회수 확인 기록 수", source)




class SearchRecoveryV235Tests(unittest.TestCase):
    def test_recovery_advice_is_specific_and_never_promises_bypass(self):
        for code in ('EMPTY_QUERY','QUERY_TOO_LONG','NETWORK','SEARCH_BLOCKED','NO_RESULTS'):
            advice=app.search_recovery_advice(code)
            self.assertEqual(advice['code'],code)
            self.assertTrue(advice['title'])
            self.assertGreaterEqual(len(advice['steps']),2)
            self.assertFalse(advice['automaticBypass'])
        self.assertFalse(app.search_recovery_advice('SEARCH_BLOCKED')['manualRetryUseful'])
        self.assertTrue(app.search_recovery_advice('NETWORK')['manualRetryUseful'])

    def test_empty_and_no_results_payloads_include_recovery(self):
        empty=app.search_public_index('   ')
        self.assertEqual(empty['error'],'EMPTY_QUERY')
        self.assertEqual(empty['recovery']['code'],'EMPTY_QUERY')
        original_cache=dict(app.SEARCH_CACHE)
        try:
            app.SEARCH_CACHE.clear()
            empty_result={'provider':'duckduckgo','error':'NO_RESULTS','message':'','results':[],'duplicateCount':0}
            with patch.object(app,'_fetch_search_provider',return_value=empty_result):
                result=app.search_public_index('recover this query')
            self.assertEqual(result['error'],'NO_RESULTS')
            self.assertEqual(result['recovery']['code'],'NO_RESULTS')
            self.assertIn('providers',result)
            self.assertIn('elapsedMs',result['providers'][0])
        finally:
            app.SEARCH_CACHE.clear();app.SEARCH_CACHE.update(original_cache)

    def test_search_recovery_ui_and_timing_history_are_connected(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['function renderSearchRecovery(query,error)', 'TikTok에서 직접 검색', 'Google에서 TikTok 영상 찾기', 'Bing에서 TikTok 영상 찾기', 'durationMs:', "'local-helper'", 'data.recovery?.manualRetryUseful', 'elapsedMs', '응답 시간', "r.elapsedMs!==undefined?esc(String(r.elapsedMs))+' ms':'—'", "renderSearchRecovery(q,'LOCAL_SERVER')"]:
            self.assertIn(marker,source)
        server=(Path(__file__).resolve().parent/'ShortCompassServer.py').read_text(encoding='utf-8')
        self.assertIn("'version':APP_VERSION",server)
        self.assertIn("APP_VERSION = '2.46'",server)




class MonetizationOpportunityTests(unittest.TestCase):
    def test_opportunity_engine_has_weighted_score_and_recommendations(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['id="oTitle"','function opportunityScore(x)','function opportunityAdvice(x)','function scoreMonetizationOpportunity()','function renderOpportunityList()','function exportOpportunitiesCsv()','addOpportunityToSources']:
            self.assertIn(marker,source)
        self.assertIn('수요 25% · 수익 적합성 20% · 차별화 15%',source)
    def test_opportunity_data_is_backup_compatible(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('monetizationOpportunities:[]',source)
        self.assertIn('out.monetizationOpportunities=Array.isArray(out.monetizationOpportunities)',source)
    def test_opportunity_score_does_not_claim_guaranteed_revenue(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('실제 시장성/수익 예측이 아닙니다.',source)
        self.assertIn('수익 보장 아님.',source)



class OpportunityLearningRegressionTests(unittest.TestCase):
    def test_experiments_can_be_attributed_to_opportunities(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['id="mOpportunity"', "opportunityId:Number(val('mOpportunity'))||null", 'function renderOpportunitySelector()', 'function opportunityExperimentStats(o)', 'function startOpportunityExperiment(id)']:
            self.assertIn(marker,source)
    def test_learning_advice_uses_actual_funnel_metrics(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['function opportunityLearningAdvice(o,st)','조회는 기록됐지만 클릭/문의가 없습니다','클릭은 있지만 전환이 없습니다','실제 실험 데이터 기반 검토','조회 1,000회당 수익']:
            self.assertIn(marker,source)
    def test_backup_and_csv_preserve_attribution(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('opportunityId:Number(v.opportunityId)||null',source)
        self.assertIn("'연결 후보'",source)
        self.assertIn("'연결 실험 수'",source)
    def test_prior_opportunity_workflow_remains_available(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ['function scoreMonetizationOpportunity()','function addOpportunityToSources(id)','function exportOpportunitiesCsv()','function normalizeImportedBackup(x)']:
            self.assertIn(marker,source)


class ABExperimentRegressionTests(unittest.TestCase):
    def test_ab_module_controls_and_result_export_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for token in ('id="abTitle"','id="abAHook"','id="abBHook"','id="abMetric"','function saveABTest()', 'function editABTest(id)', 'function renderABTests()', 'function exportABTestsCsv()', 'function assessABTest(test)'):
            self.assertIn(token, source)
        self.assertIn('조회수 1,000회 이상', source)
        self.assertIn('통계적 유의성 검정', source)

    def test_ab_data_roundtrips_through_json_backup(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('abTests:[]', source)
        self.assertIn('out.abTests=Array.isArray(out.abTests)', source)
        self.assertIn('function normalizeABTest(v,i=0)', source)
        self.assertIn('if(x.abTests!==undefined&&!Array.isArray(x.abTests))', source)

    def test_ab_comparison_uses_conversion_and_revenue_denominators(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('v.clicks>0&&v.conversions!==null', source)
        self.assertIn('v.views>0&&v.revenue!==null', source)
        self.assertIn('abDateMatured(a)&&abDateMatured(b)', source)
        self.assertIn('function clearABForm(showMessage=true)', source)



class ABReliabilityV233Tests(unittest.TestCase):
    def test_observation_dates_and_uncertainty_helpers_exist(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ('id="abAObserved"','id="abBObserved"','function validABDate(value)','function abDaysBetween(start,end)','function abWilsonInterval(successes,total,z=1.96)','function abMetricUncertainty(test)','function abQualityWarnings(test)','function abNextAction(test,data)'):
            self.assertIn(marker,source)

    def test_observation_date_and_quality_diagnostics_are_exported(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in ('A 성과 확인일','B 성과 확인일','품질 경고','다음 행동','관찰 기간이 A/B 간 1일 넘게','조회수 차이가 3배 이상'):
            self.assertIn(marker,source)
        self.assertIn("'version':APP_VERSION", (Path(__file__).resolve().parent/'ShortCompassServer.py').read_text(encoding='utf-8'))

    def test_rpm_does_not_claim_a_fake_statistical_interval(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertIn('수익은 상품 구성·정산 지연·시청자 구성에 크게 좌우됩니다',source)
        self.assertIn('정식 차이 검정이나 p값이 아닙니다',source)
        self.assertIn('반복 실험',source)



class V233InteractiveRegressionTests(unittest.TestCase):
    def test_diagnostic_search_retry_has_unique_id_and_a_click_handler(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        self.assertEqual(source.count('id="runPublicIndexSearch"'),1)
        self.assertIn('data-run-public-search-again="1"',source)
        self.assertIn("root.querySelector('[data-run-public-search-again]')?.addEventListener('click',()=>runPublicIndexSearch",source)



class YouTubeRankingCarryForwardTests(unittest.TestCase):
    def test_live_search_has_explicit_local_ranking_and_export(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortsCompass.html').read_text(encoding='utf-8')
        for marker in [
            'function youtubeNumber(value)', 'function youtubeViewsPerDay(item,now=Date.now())',
            'function sortYouTubeDetails(items,searchIds,sortMode,now=Date.now())',
            "sortYouTubeDetails(rawItems,ids,order,collectedAtMs)", "order==='velocity'?'date':order",
            '검색 결과 CSV 내보내기', "rankingScope:'요청한 검색 결과 표본 안에서 정렬'",
            '상세 통계의 실제 조회수로 내림차순 재정렬했습니다.',
            '전체 YouTube 영상의 절대 순위는 아닙니다.', "<option>50</option>",
            'function exportLiveYouTubeCsv()'
        ]:
            self.assertIn(marker,source)

    def test_server_version_is_v245(self):
        from pathlib import Path
        source=(Path(__file__).resolve().parent/'ShortCompassServer.py').read_text(encoding='utf-8')
        self.assertIn("APP_VERSION = '2.46'",source)



if __name__=='__main__':
    unittest.main(verbosity=2)
