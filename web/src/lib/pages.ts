/** Complete a bounded observable query; never show a silently truncated newest window. */
export async function collectPages<T>(read:(offset:number,limit:number)=>Promise<{records:T[];analysis_limit:number}>,pageSize=5000):Promise<{records:T[]}> {
  const records:T[]=[];let budget:number|undefined;
  for(;;){const page=await read(records.length,pageSize);budget??=page.analysis_limit;
    if(budget===undefined||!Number.isSafeInteger(budget)||budget<1)throw new Error('Server did not declare a valid history budget. Reload the updated SIRE server.');
    if(records.length+page.records.length>budget)throw new Error('History exceeds the analysis budget. Choose a shorter window; no partial latest-window chart is shown.');
    records.push(...page.records);if(page.records.length<pageSize)return {records};
  }
}
