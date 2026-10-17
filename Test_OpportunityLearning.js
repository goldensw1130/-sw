'use strict';
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(__dirname + '/ShortsCompass.html', 'utf8');
function sourceLine(name) {
  const line = html.split(/\r?\n/).find(x => x.startsWith('function ' + name + '('));
  if (!line) throw new Error('Missing function: ' + name);
  return line;
}
const context = { state: { monetizationOpportunities: [], monetizationExperiments: [] }, console };
const names = ['opportunityScore', 'opportunityExperimentStats', 'opportunityComparableStats', 'percentileRank', 'opportunityEmpiricalRanking'];
vm.createContext(context);
vm.runInContext(names.map(sourceLine).join('\n') + `
(function(){
 const assert=(v,m)=>{if(!v)throw new Error(m)};
 const mkOpp=(id,score)=>({id,title:'Candidate '+id,score,demand:3,monetization:3,originality:3,ease:3,credibility:3,competition:3});
 const mkRows=(id,conv,rev,platform='YouTube Shorts',model='affiliate')=>[
  {opportunityId:id,platform,model,views:1000,clicks:10,conversions:conv,revenue:rev/3,reported:{views:true,clicks:true,conversions:true,revenue:true}},
  {opportunityId:id,platform,model,views:1000,clicks:10,conversions:conv,revenue:rev/3,reported:{views:true,clicks:true,conversions:true,revenue:true}},
  {opportunityId:id,platform,model,views:1000,clicks:10,conversions:conv,revenue:rev/3,reported:{views:true,clicks:true,conversions:true,revenue:true}}
 ];
 // Same three eligible candidates in the same cohort can receive an empirical index.
 state.monetizationOpportunities=[mkOpp(1,80),mkOpp(2,70),mkOpp(3,60)];
 state.monetizationExperiments=[...mkRows(1,5,900),...mkRows(2,3,600),...mkRows(3,1,90)];
 let result=opportunityEmpiricalRanking();
 assert(result.qualified.length===3,'three qualified comparable candidates should be ranked');
 assert(result.qualified.every(x=>x.adjustedScore!==null && x.cohortSize===3),'qualified candidate scores should include cohort metadata');
 assert(result.qualified[0].o.id===1,'best base and empirical candidate should rank first');
 // A single candidate must not receive a misleading within-cohort score.
 state.monetizationOpportunities=[mkOpp(1,80)];
 state.monetizationExperiments=[...mkRows(1,5,900)];
 result=opportunityEmpiricalRanking();
 assert(result.qualified.length===0 && result.needs.length===1,'one candidate is insufficient for comparative ranking');
 assert(result.needs[0].adjustedScore===null,'insufficient data must keep base-only scoring');
 // Mixing platforms / monetization paths must block aggregation.
 state.monetizationOpportunities=[mkOpp(1,80),mkOpp(2,70),mkOpp(3,60)];
 state.monetizationExperiments=[...mkRows(1,5,900,'YouTube Shorts','affiliate'),...mkRows(1,5,900,'TikTok','affiliate'),...mkRows(2,3,600),...mkRows(3,1,90)];
 result=opportunityEmpiricalRanking();
 const mixed=result.all.find(x=>x.o.id===1);
 assert(!mixed.empirical.eligible && /섞여/.test(mixed.empirical.reason),'mixed data should be rejected as incomparable');
 // Two eligible candidates still cannot establish a meaningful shared ranking.
 state.monetizationOpportunities=[mkOpp(1,80),mkOpp(2,70)];
 state.monetizationExperiments=[...mkRows(1,5,900),...mkRows(2,3,600)];
 result=opportunityEmpiricalRanking();
 assert(result.qualified.length===0,'cohort must contain at least three eligible candidates');
 // Partial reporting must not let unknown values contaminate aggregate metrics.
 state.monetizationOpportunities=[mkOpp(1,80)];
 state.monetizationExperiments=[
  {opportunityId:1,platform:'YouTube Shorts',model:'affiliate',views:1000,clicks:10,conversions:2,revenue:100,reported:{views:true,clicks:true,conversions:true,revenue:true}},
  {opportunityId:1,platform:'YouTube Shorts',model:'affiliate',views:2000,clicks:20,conversions:4,revenue:200,reported:{views:false,clicks:true,conversions:true,revenue:false}}
 ];
 const stats=opportunityExperimentStats({id:1});
 assert(stats.views===1000 && stats.revenue===100,'unknown views/revenue must not enter sums');
 assert(stats.coverage.views===1 && stats.coverage.revenue===1 && stats.rows.length===2,'coverage must show partial reporting');
 assert(stats.ctr===null && stats.rpm===null,'aggregate rates require full metric coverage');
 // A legacy or partially blank metric must not be silently interpreted as zero.
 state.monetizationOpportunities=[mkOpp(1,80),mkOpp(2,70),mkOpp(3,60)];
 state.monetizationExperiments=[...mkRows(1,5,900),...mkRows(2,3,600),...mkRows(3,1,90)];
 state.monetizationExperiments[0].reported.revenue=false;
 result=opportunityEmpiricalRanking();
 assert(result.qualified.length===0,'two remaining candidates are still too few for cohort ranking');
 assert(result.all.find(x=>x.o.id===1).adjustedScore===null,'candidate with unreported revenue must not qualify');
 assert(/빈칸은 0으로/.test(result.all.find(x=>x.o.id===1).empirical.reason),'missing metrics must be identified as unknown, not zero');
 console.log('Opportunity learning runtime checks: 6 passed');
})();`, context);
